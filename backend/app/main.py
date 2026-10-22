import json
import logging
import threading
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

from . import agenda, config, db, llm
from .call_service import schedule_appointment_call
from .email_service import send_appointment_email
from .embeddings import get_embedding_function, get_qdrant_client
from .rag_engine import answer_question, answer_question_stream
from .security import rate_limit, require_admin, tokens_match, verify_vapi_secret

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Asistente Unilibre — Backend RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)


@app.on_event("startup")
def _on_startup():
    db.init_db()
    if not config.ADMIN_API_KEY:
        log.warning("ADMIN_API_KEY vacío: el panel del asesor (/admin/*) queda deshabilitado.")
    # Precarga en segundo plano: el modelo de embeddings, la base vectorial y el LLM
    # tardan en cargarse; así la primera pregunta del día no paga esa espera.
    threading.Thread(target=_warm_up, daemon=True).start()


def _warm_up():
    try:
        embeddings, _ = _get_resources()
        embeddings.embed_query("precarga")
        llm.warm_up()
        log.info("Precarga lista: embeddings y modelo en memoria.")
    except Exception as exc:  # el backend sigue funcionando; solo se pierde la precarga
        log.warning("No se pudo precargar: %s", exc)


_embeddings = None
_qdrant_client = None


def _get_resources():
    global _embeddings, _qdrant_client
    if _embeddings is None:
        _embeddings = get_embedding_function()
    if _qdrant_client is None:
        _qdrant_client = get_qdrant_client()
    return _embeddings, _qdrant_client


@app.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------------- preguntas

class HistoryTurn(BaseModel):
    role: str
    text: str = Field(max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=12)


class AskResponse(BaseModel):
    answer: str
    sources: list[str]


@app.post("/ask", response_model=AskResponse, dependencies=[Depends(rate_limit)])
def ask(payload: AskRequest):
    embeddings, qdrant_client = _get_resources()
    history = [t.model_dump() for t in payload.history]
    result = answer_question(payload.question, embeddings, qdrant_client, history)
    return AskResponse(**result)


@app.post("/ask/stream", dependencies=[Depends(rate_limit)])
def ask_stream(payload: AskRequest):
    """Igual que /ask, pero envía la respuesta a medida que se escribe (una línea JSON
    por evento), para que el chat muestre texto en vez de esperar la respuesta completa."""
    embeddings, qdrant_client = _get_resources()
    history = [t.model_dump() for t in payload.history]

    def events():
        try:
            for event in answer_question_stream(payload.question, embeddings, qdrant_client, history):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as exc:
            log.warning("Error respondiendo '%s': %s", payload.question[:80], exc)
            yield json.dumps({"type": "error", "detail": str(exc)}, ensure_ascii=False) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")


# ----------------------------------------------------------------- agenda

@app.get("/availability", dependencies=[Depends(rate_limit)])
def availability(tipo: str = "Admisiones", limit: int = 3):
    """Próximas franjas libres reales para ese tipo de atención."""
    return {"slots": agenda.available_slots(tipo, limit=max(1, min(limit, 6)))}


class AppointmentRequest(BaseModel):
    tipo: str = Field(max_length=80)
    modalidad: str = Field(max_length=40)
    slot_label: str = Field(max_length=120)
    slot_iso: str = Field(max_length=40)
    asesor: str = Field(max_length=80)
    email: EmailStr
    telefono: str | None = Field(default=None, max_length=20)
    nombre: str | None = Field(default=None, max_length=120)
    programa: str | None = Field(default=None, max_length=120)
    sede: str | None = Field(default=None, max_length=80)
    necesidad: str | None = Field(default=None, max_length=500)
    transcript: list[HistoryTurn] = Field(default_factory=list, max_length=20)


class AppointmentResponse(BaseModel):
    id: int
    token: str
    slot_iso: str
    slot_label: str
    asesor: str
    email_sent: bool
    email_detail: str


def _check_slot(slot_iso: str, asesor: str) -> str:
    """Valida que la franja exista, sea futura y esté libre. Devuelve su etiqueta oficial."""
    dt = agenda.parse_slot(slot_iso)
    if not dt or dt <= datetime.now(agenda.BOGOTA):
        raise HTTPException(status_code=422, detail="La fecha de la cita no es válida.")
    known = {a["nombre"] for a in agenda.load_agenda()["asesores"]}
    if asesor not in known:
        raise HTTPException(status_code=422, detail="Asesor desconocido.")
    if not agenda.is_slot_free(dt.isoformat(), asesor):
        raise HTTPException(status_code=409, detail="Esa franja ya fue tomada. Elige otro horario.")
    return agenda.format_slot(dt)


def _email_status(sent: bool, detail: str) -> str:
    return "sent" if sent else ("simulated" if detail.startswith("simulated") else "failed")


@app.post("/appointments", response_model=AppointmentResponse, dependencies=[Depends(rate_limit)])
def create_appointment(payload: AppointmentRequest):
    data = payload.model_dump()
    dt = agenda.parse_slot(payload.slot_iso)
    data["slot_label"] = _check_slot(payload.slot_iso, payload.asesor)
    data["slot_iso"] = dt.isoformat()
    appointment_id, token = db.insert_appointment(data)
    appointment = db.get_appointment(appointment_id)

    sent, detail = send_appointment_email(appointment, "confirmada")
    db.update_email_status(appointment_id, _email_status(sent, detail))

    return AppointmentResponse(
        id=appointment_id, token=token, slot_iso=data["slot_iso"], slot_label=data["slot_label"],
        asesor=payload.asesor, email_sent=sent, email_detail=detail,
    )


def _owned_appointment(appointment_id: int, token: str | None) -> dict:
    """La cita solo la puede ver o cambiar quien tiene su código de acceso."""
    appointment = db.get_appointment(appointment_id)
    if not appointment or not tokens_match(token, appointment.get("access_token")):
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    return appointment


def _public_view(a: dict) -> dict:
    keys = ("id", "tipo", "modalidad", "slot_iso", "slot_label", "asesor", "programa", "sede", "status")
    return {k: a.get(k) for k in keys}


class TokenRequest(BaseModel):
    token: str


@app.post("/appointments/{appointment_id}/status", dependencies=[Depends(rate_limit)])
def appointment_status(appointment_id: int, payload: TokenRequest):
    """Estado actual de una cita (lo usan "Mis citas" y "Mi proceso" para sincronizarse)."""
    return _public_view(_owned_appointment(appointment_id, payload.token))


@app.post("/appointments/{appointment_id}/cancel", dependencies=[Depends(rate_limit)])
def cancel_appointment(appointment_id: int, payload: TokenRequest):
    appointment = _owned_appointment(appointment_id, payload.token)
    if appointment["status"] not in db.ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Esta cita ya no está activa.")
    db.update_status(appointment_id, "cancelada")
    appointment = db.get_appointment(appointment_id)
    send_appointment_email(appointment, "cancelada")
    return _public_view(appointment)


class RescheduleRequest(BaseModel):
    token: str
    slot_iso: str = Field(max_length=40)
    asesor: str = Field(max_length=80)


@app.post("/appointments/{appointment_id}/reschedule", dependencies=[Depends(rate_limit)])
def reschedule_appointment(appointment_id: int, payload: RescheduleRequest):
    appointment = _owned_appointment(appointment_id, payload.token)
    if appointment["status"] not in db.ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Esta cita ya no está activa.")
    label = _check_slot(payload.slot_iso, payload.asesor)
    db.reschedule(appointment_id, agenda.parse_slot(payload.slot_iso).isoformat(), label, payload.asesor)
    appointment = db.get_appointment(appointment_id)
    send_appointment_email(appointment, "reprogramada")
    return _public_view(appointment)


class CallResponse(BaseModel):
    call_scheduled: bool
    call_detail: str


@app.post("/appointments/{appointment_id}/call", response_model=CallResponse,
          dependencies=[Depends(rate_limit)])
def call_appointment(appointment_id: int, payload: TokenRequest):
    """Llamada de confirmación con Vapi. Requiere el código de la cita y se hace una sola
    vez por cita: cada llamada real tiene costo."""
    appointment = _owned_appointment(appointment_id, payload.token)
    if appointment["call_status"] not in ("not_scheduled", "failed"):
        return CallResponse(call_scheduled=False, call_detail="already_requested")

    scheduled, detail = schedule_appointment_call(appointment)
    if scheduled:
        status = "scheduled"
    elif detail == "no_phone":
        status = "no_phone"
    elif detail.startswith("simulated"):
        status = "simulated"
    else:
        status = "failed"
    db.update_call_status(appointment_id, status)

    return CallResponse(call_scheduled=scheduled, call_detail=detail)


@app.post("/webhooks/vapi", dependencies=[Depends(verify_vapi_secret)])
async def vapi_webhook(request: Request):
    """Recibe los eventos de Vapi durante/al final de la llamada. Solo se aceptan si traen
    el secreto configurado (x-vapi-secret). La forma exacta del payload depende de la
    configuración del asistente en Vapi — este handler es defensivo (usa .get() en todo)."""
    payload = await request.json()
    message = payload.get("message", {})
    call = message.get("call", {}) or {}
    appointment_id = (call.get("metadata") or {}).get("appointment_id")

    if appointment_id is None:
        return {"received": True}

    msg_type = message.get("type")
    if msg_type == "end-of-call-report":
        db.save_call_result(
            int(appointment_id),
            "completed",
            message.get("transcript"),
            message.get("summary"),
        )
    elif msg_type == "status-update" and message.get("status"):
        db.update_call_status(int(appointment_id), f"vapi:{message['status']}")

    return {"received": True}


# ------------------------------------------------------ panel del asesor

@app.get("/admin/appointments", dependencies=[Depends(require_admin)])
def admin_appointments(status: str | None = None):
    rows = db.list_appointments(status=status)
    for row in rows:
        row.pop("access_token", None)
    return {"appointments": rows}


class StatusUpdate(BaseModel):
    status: str


@app.patch("/admin/appointments/{appointment_id}", dependencies=[Depends(require_admin)])
def admin_update_appointment(appointment_id: int, payload: StatusUpdate):
    if not db.get_appointment(appointment_id):
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    try:
        db.update_status(appointment_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = db.get_appointment(appointment_id)
    row.pop("access_token", None)
    return row


@app.get("/admin/unanswered", dependencies=[Depends(require_admin)])
def admin_unanswered():
    """Preguntas que el agente no supo responder: lo que falta en el documento."""
    return {"questions": db.list_unanswered()}
