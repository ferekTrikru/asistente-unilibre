"""Envío del correo de confirmación de cita, por dos vías posibles (en este orden):

1. SMTP con tu propia cuenta de correo (ej. Gmail + "contraseña de aplicación") — no
   requiere crear cuenta en ningún servicio externo, solo generar esa clave en tu cuenta
   de Google. Ver backend/README.md para el paso a paso.
2. Resend (https://resend.com) — requiere una cuenta gratis y una API key.

Sin ninguna de las dos configuradas, el envío se simula (se registra en consola en vez
de enviarse) para que el flujo de agendamiento funcione en un demo sin credenciales."""
import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from . import config

RESEND_URL = "https://api.resend.com/emails"

# Un mismo correo para los tres momentos de la cita: (asunto, título).
_KINDS = {
    "confirmada": ("Tu cita con la Universidad Libre está confirmada",
                   "Tu cita con la Universidad Libre quedó confirmada"),
    "reprogramada": ("Tu cita con la Universidad Libre fue reprogramada",
                     "Tu cita con la Universidad Libre tiene nueva fecha"),
    "cancelada": ("Tu cita con la Universidad Libre fue cancelada",
                  "Tu cita con la Universidad Libre fue cancelada"),
}


def _build_html(appointment: dict, kind: str) -> str:
    # Los datos vienen del aspirante: se escapan para que no puedan inyectar HTML.
    e = {k: html.escape(str(v)) for k, v in appointment.items() if v is not None and not isinstance(v, list)}
    programa = e.get("programa") or "tu proceso de admisión"
    sede_line = f"<p><strong>Sede:</strong> {e['sede']}</p>" if e.get("sede") else ""
    title = _KINDS[kind][1]
    closing = ("Si quieres una nueva cita, vuelve al chat de admisiones."
               if kind == "cancelada"
               else "Si necesitas reprogramar o cancelar, hazlo desde «Mis citas» en el chat de admisiones.")
    return f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <div style="background:#c8102e; color:#fff; padding:16px 20px; border-bottom:4px solid #f2a900;">
        <strong style="font-size:17px;">Universidad Libre · Admisiones Barranquilla</strong>
      </div>
      <h2 style="color:#c8102e;">{title}</h2>
      <p>Hola{f" {e['nombre']}" if e.get('nombre') else ''}, este es el resumen de tu cita:</p>
      <p><strong>Tipo de atención:</strong> {e.get('tipo', '')}</p>
      <p><strong>Modalidad:</strong> {e.get('modalidad', '')}</p>
      <p><strong>Fecha y hora:</strong> {e.get('slot_label', '')}</p>
      <p><strong>Asesor asignado:</strong> {e.get('asesor', '')}</p>
      {sede_line}
      <p><strong>Programa de interés:</strong> {programa}</p>
      <p>{closing}</p>
      <p style="color:#8a0b1f; font-style:italic;">Scientia Fons Libertatis</p>
    </div>
    """.strip()


def _send_via_smtp(appointment: dict, kind: str) -> tuple[bool, str]:
    message = MIMEMultipart("alternative")
    message["Subject"] = _KINDS[kind][0]
    message["From"] = f"{config.SMTP_FROM_NAME} <{config.SMTP_USER}>"
    message["To"] = appointment["email"]
    message.attach(MIMEText(_build_html(appointment, kind), "html"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_APP_PASSWORD)
            server.sendmail(config.SMTP_USER, [appointment["email"]], message.as_string())
        return True, "sent (smtp)"
    except smtplib.SMTPException as exc:
        return False, f"error (smtp): {exc}"


def _send_via_resend(appointment: dict, kind: str) -> tuple[bool, str]:
    payload = {
        "from": f"{config.RESEND_FROM_NAME} <{config.RESEND_FROM_EMAIL}>",
        "to": [appointment["email"]],
        "subject": _KINDS[kind][0],
        "html": _build_html(appointment, kind),
    }
    try:
        response = httpx.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
            timeout=10,
        )
        response.raise_for_status()
        return True, "sent (resend)"
    except httpx.HTTPError as exc:
        return False, f"error (resend): {exc}"


def send_appointment_email(appointment: dict, kind: str = "confirmada") -> tuple[bool, str]:
    """Devuelve (enviado, detalle). No lanza excepción: un fallo de correo nunca debe
    tumbar el agendamiento de la cita."""
    if config.SMTP_USER and config.SMTP_APP_PASSWORD:
        return _send_via_smtp(appointment, kind)

    if config.RESEND_API_KEY:
        return _send_via_resend(appointment, kind)

    print(f"[email simulado] Cita {kind} #{appointment.get('id')} para "
          f"{appointment['email']} — {appointment['tipo']} el {appointment['slot_label']}")
    return False, "simulated (no hay SMTP_USER/SMTP_APP_PASSWORD ni RESEND_API_KEY configurados)"
