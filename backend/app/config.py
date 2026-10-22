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
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Asistente Combarranquilla — Admisiones")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")
RESEND_FROM_NAME = os.environ.get("RESEND_FROM_NAME", "Asistente Combarranquilla — Admisiones")

# Vapi (https://vapi.ai) — llamada saliente con un agente de voz con IA para confirmar
# la cita. Sin estas variables, la llamada se simula (se registra en consola).
VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "")
VAPI_ASSISTANT_ID = os.environ.get("VAPI_ASSISTANT_ID", "")
VAPI_PHONE_NUMBER_ID = os.environ.get("VAPI_PHONE_NUMBER_ID", "")

CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
