"""Llamada saliente de confirmación de cita vía Vapi (https://vapi.ai) — un agente de
voz con IA que llama al aspirante para confirmar los datos de la cita.

Sin VAPI_API_KEY/VAPI_ASSISTANT_ID/VAPI_PHONE_NUMBER_ID configuradas, la llamada se
simula (se registra en consola) para que el flujo funcione en un demo sin credenciales
reales. El agente de voz (creado y configurado en el dashboard de Vapi) debe restringirse
a lo mismo que puede responder el chat: confirmar/reprogramar/cancelar la cita y
preguntas básicas de la base de conocimiento — nunca inventar información."""
import httpx

from . import config

VAPI_CALL_URL = "https://api.vapi.ai/call"


def _first_message(appointment: dict) -> str:
    return (
        f"Hola, te llamo del área de admisiones de Combarranquilla para confirmar "
        f"tu cita de {appointment['tipo']} el {appointment['slot_label']}. "
        f"¿Puedes confirmarme si asistirás?"
    )


def schedule_appointment_call(appointment: dict) -> tuple[bool, str]:
    """Devuelve (programada, detalle). No lanza excepción: un fallo en la llamada nunca
    debe tumbar el agendamiento de la cita."""
    if not appointment.get("telefono"):
        return False, "no_phone"

    if not (config.VAPI_API_KEY and config.VAPI_ASSISTANT_ID and config.VAPI_PHONE_NUMBER_ID):
        print(f"[llamada simulada] Confirmación de cita #{appointment.get('id')} a "
              f"{appointment['telefono']} — {appointment['tipo']} el {appointment['slot_label']}")
        return False, ("simulated (VAPI_API_KEY/VAPI_ASSISTANT_ID/VAPI_PHONE_NUMBER_ID "
                        "no configurados)")

    payload = {
        "assistantId": config.VAPI_ASSISTANT_ID,
        "phoneNumberId": config.VAPI_PHONE_NUMBER_ID,
        "customer": {"number": appointment["telefono"]},
        "assistantOverrides": {
            "firstMessage": _first_message(appointment),
            "variableValues": {
                "nombre": appointment.get("nombre") or "",
                "tipo": appointment["tipo"],
                "modalidad": appointment["modalidad"],
                "fecha_hora": appointment["slot_label"],
                "asesor": appointment["asesor"],
                "programa": appointment.get("programa") or "",
                "sede": appointment.get("sede") or "",
            },
        },
        "metadata": {"appointment_id": appointment.get("id")},
    }

    try:
        response = httpx.post(
            VAPI_CALL_URL,
            json=payload,
            headers={"Authorization": f"Bearer {config.VAPI_API_KEY}"},
            timeout=10,
        )
        response.raise_for_status()
        return True, "scheduled"
    except httpx.HTTPError as exc:
        return False, f"error: {exc}"
