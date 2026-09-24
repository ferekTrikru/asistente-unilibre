from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from . import config, db
from .call_service import schedule_appointment_call
from .email_service import send_appointment_email
from .embeddings import get_embedding_function, get_qdrant_client
from .rag_engine import answer_question

app = FastAPI(title="Asistente Combarranquilla — Backend RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup():
    db.init_db()


_embeddings = None
_qdrant_client = None


def _get_resources():
    global _embeddings, _qdrant_client
    if _embeddings is None:
        _embeddings = get_embedding_function()
    if _qdrant_client is None:
        _qdrant_client = get_qdrant_client()
    return _embeddings, _qdrant_client


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[str]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest):
    embeddings, qdrant_client = _get_resources()
    result = answer_question(payload.question, embeddings, qdrant_client)
    return AskResponse(**result)


class AppointmentRequest(BaseModel):
    tipo: str
    modalidad: str
    slot_label: str
    slot_iso: str
    asesor: str
    email: EmailStr
    telefono: str | None = None
    nombre: str | None = None
    programa: str | None = None
    sede: str | None = None
    necesidad: str | None = None


class AppointmentResponse(BaseModel):
    id: int
    email_sent: bool
    email_detail: str


@app.post("/appointments", response_model=AppointmentResponse)
def create_appointment(payload: AppointmentRequest):
    appointment_id = db.insert_appointment(payload.model_dump())
    appointment = db.get_appointment(appointment_id)

    sent, detail = send_appointment_email(appointment)
    status = "sent" if sent else ("simulated" if detail.startswith("simulated") else "failed")
    db.update_email_status(appointment_id, status)

    return AppointmentResponse(id=appointment_id, email_sent=sent, email_detail=detail)


class CallResponse(BaseModel):
    call_scheduled: bool
    call_detail: str


@app.post("/appointments/{appointment_id}/call", response_model=CallResponse)
def call_appointment(appointment_id: int):
    appointment = db.get_appointment(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

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


@app.post("/webhooks/vapi")
async def vapi_webhook(request: Request):
    """Recibe los eventos de Vapi durante/al final de la llamada. La forma exacta del
    payload depende de la configuración del asistente en el dashboard de Vapi — este
    handler es defensivo (usa .get() en todo) para no romperse si cambia."""
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
