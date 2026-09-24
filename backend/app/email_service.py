"""Envío del correo de confirmación de cita, por dos vías posibles (en este orden):

1. SMTP con tu propia cuenta de correo (ej. Gmail + "contraseña de aplicación") — no
   requiere crear cuenta en ningún servicio externo, solo generar esa clave en tu cuenta
   de Google. Ver backend/README.md para el paso a paso.
2. Resend (https://resend.com) — requiere una cuenta gratis y una API key.

Sin ninguna de las dos configuradas, el envío se simula (se registra en consola en vez
de enviarse) para que el flujo de agendamiento funcione en un demo sin credenciales."""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from . import config

RESEND_URL = "https://api.resend.com/emails"
SUBJECT = "Tu cita con Combarranquilla está confirmada"


def _build_html(appointment: dict) -> str:
    programa = appointment.get("programa") or "tu proceso de admisión"
    sede = appointment.get("sede")
    sede_line = f"<p><strong>Sede:</strong> {sede}</p>" if sede else ""
    return f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color:#007a3d;">Tu cita con Combarranquilla quedó confirmada</h2>
      <p>Hola{f" {appointment['nombre']}" if appointment.get('nombre') else ''}, este es el resumen de tu cita:</p>
      <p><strong>Tipo de atención:</strong> {appointment['tipo']}</p>
      <p><strong>Modalidad:</strong> {appointment['modalidad']}</p>
      <p><strong>Fecha y hora:</strong> {appointment['slot_label']}</p>
      <p><strong>Asesor asignado:</strong> {appointment['asesor']}</p>
      {sede_line}
      <p><strong>Programa de interés:</strong> {programa}</p>
      <p>Si necesitas reprogramar o cancelar, responde este correo o vuelve al chat de admisiones.</p>
    </div>
    """.strip()


def _send_via_smtp(appointment: dict) -> tuple[bool, str]:
    message = MIMEMultipart("alternative")
    message["Subject"] = SUBJECT
    message["From"] = f"{config.SMTP_FROM_NAME} <{config.SMTP_USER}>"
    message["To"] = appointment["email"]
    message.attach(MIMEText(_build_html(appointment), "html"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_APP_PASSWORD)
            server.sendmail(config.SMTP_USER, [appointment["email"]], message.as_string())
        return True, "sent (smtp)"
    except smtplib.SMTPException as exc:
        return False, f"error (smtp): {exc}"


def _send_via_resend(appointment: dict) -> tuple[bool, str]:
    payload = {
        "from": f"{config.RESEND_FROM_NAME} <{config.RESEND_FROM_EMAIL}>",
        "to": [appointment["email"]],
        "subject": SUBJECT,
        "html": _build_html(appointment),
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


def send_appointment_email(appointment: dict) -> tuple[bool, str]:
    """Devuelve (enviado, detalle). No lanza excepción: un fallo de correo nunca debe
    tumbar el agendamiento de la cita."""
    if config.SMTP_USER and config.SMTP_APP_PASSWORD:
        return _send_via_smtp(appointment)

    if config.RESEND_API_KEY:
        return _send_via_resend(appointment)

    print(f"[email simulado] Confirmación de cita #{appointment.get('id')} para "
          f"{appointment['email']} — {appointment['tipo']} el {appointment['slot_label']}")
    return False, "simulated (no hay SMTP_USER/SMTP_APP_PASSWORD ni RESEND_API_KEY configurados)"
