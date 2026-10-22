import os

from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
QDRANT_LOCAL_PATH = os.environ.get("QDRANT_LOCAL_PATH", "./qdrant_data")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "admisiones_unilibre")

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
EMBEDDING_DIM = 384

DATA_PATH = os.environ.get("DATA_PATH", "data")

APPOINTMENTS_DB_PATH = os.environ.get("APPOINTMENTS_DB_PATH", "data/appointments.db")

# Envío del correo de confirmación de cita. Dos formas, en orden de prioridad:
# 1. SMTP con tu propia cuenta de correo (ej. Gmail + "contraseña de aplicación") —
#    no requiere crear cuenta en ningún servicio externo.
# 2. Resend (https://resend.com) — requiere una cuenta gratis y una API key.
# Sin ninguna de las dos, el envío se simula (se registra en consola).
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_APP_PASSWORD = os.environ.get("SMTP_APP_PASSWORD", "")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Universidad Libre — Admisiones Barranquilla")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")
RESEND_FROM_NAME = os.environ.get("RESEND_FROM_NAME", "Universidad Libre — Admisiones Barranquilla")

# Vapi (https://vapi.ai) — llamada saliente con un agente de voz con IA para confirmar
# la cita. Sin estas variables, la llamada se simula (se registra en consola).
VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "")
VAPI_ASSISTANT_ID = os.environ.get("VAPI_ASSISTANT_ID", "")
VAPI_PHONE_NUMBER_ID = os.environ.get("VAPI_PHONE_NUMBER_ID", "")

# Secreto que Vapi envía en el encabezado x-vapi-secret de cada webhook (se define en el
# dashboard de Vapi, campo "Server URL Secret"). Si está vacío, el webhook se rechaza.
VAPI_WEBHOOK_SECRET = os.environ.get("VAPI_WEBHOOK_SECRET", "")

# Clave del panel del asesor (/admin/*). Sin ella el panel queda deshabilitado.
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")

# Límite de peticiones por IP y por minuto para las rutas públicas (protege de abuso:
# cada pregunta ocupa la GPU varios segundos y cada llamada de Vapi cuesta dinero).
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "20"))

# Agenda de asesores (horario de atención y quién atiende cada tipo de cita).
ADVISORS_PATH = os.environ.get("ADVISORS_PATH", "config/advisors.json")

_DEFAULT_ORIGINS = "http://localhost:5000,http://127.0.0.1:5000,http://localhost:8080"
CORS_ORIGINS = [
    origin.strip()
    for origin in (os.environ.get("CORS_ORIGINS") or _DEFAULT_ORIGINS).split(",")
    if origin.strip()
]
