"""Persistencia en SQLite (sin ORM: suficiente para el volumen de una seccional — dos
tablas y migraciones simples que agregan columnas sin borrar datos)."""
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

# Estados de una cita. Las "activas" ocupan la franja del asesor en la agenda.
STATUSES = ("confirmada", "reprogramada", "asistio", "no_asistio", "admitido", "cancelada")
ACTIVE_STATUSES = ("confirmada", "reprogramada")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    modalidad TEXT NOT NULL,
    slot_label TEXT NOT NULL,
    slot_iso TEXT NOT NULL,
    asesor TEXT NOT NULL,
    programa TEXT,
    sede TEXT,
    necesidad TEXT,
    nombre TEXT,
    email TEXT NOT NULL,
    telefono TEXT,
    email_status TEXT NOT NULL DEFAULT 'pending',
    call_status TEXT NOT NULL DEFAULT 'not_scheduled',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS unanswered_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# Columnas agregadas después de la primera versión: se crean si faltan.
_NEW_COLUMNS = {
    "call_transcript": "TEXT",
    "call_summary": "TEXT",
    "status": "TEXT NOT NULL DEFAULT 'confirmada'",
    "access_token": "TEXT",
    "chat_transcript": "TEXT",
    "updated_at": "TEXT",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_connection():
    conn = sqlite3.connect(config.APPOINTMENTS_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(conn):
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(appointments)")}
    for column, ddl in _NEW_COLUMNS.items():
        if column not in existing_cols:
            conn.execute(f"ALTER TABLE appointments ADD COLUMN {column} {ddl}")


def init_db():
    with get_connection() as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)


def _row_to_dict(row) -> dict:
    data = dict(row)
    if data.get("chat_transcript"):
        try:
            data["chat_transcript"] = json.loads(data["chat_transcript"])
        except ValueError:
            data["chat_transcript"] = []
    return data


# ---------------------------------------------------------------- citas

def insert_appointment(data: dict) -> tuple[int, str]:
    """Guarda la cita y devuelve (id, código de acceso). El código es lo que permite al
    aspirante consultar, cancelar o reprogramar su cita sin tener cuenta."""
    token = secrets.token_urlsafe(16)
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO appointments
                (tipo, modalidad, slot_label, slot_iso, asesor, programa, sede, necesidad,
                 nombre, email, telefono, email_status, call_status, status, access_token,
                 chat_transcript, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'not_scheduled', 'confirmada', ?, ?, ?, ?)
            """,
            (
                data["tipo"], data["modalidad"], data["slot_label"], data["slot_iso"],
                data["asesor"], data.get("programa"), data.get("sede"), data.get("necesidad"),
                data.get("nombre"), data["email"], data.get("telefono"), token,
                json.dumps(data.get("transcript") or [], ensure_ascii=False),
                _now(), _now(),
            ),
        )
        return cursor.lastrowid, token


def get_appointment(appointment_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
        return _row_to_dict(row) if row else None


def list_appointments(status: str | None = None, limit: int = 200) -> list[dict]:
    query = "SELECT * FROM appointments"
    params: tuple = ()
    if status:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY slot_iso DESC LIMIT ?"
    with get_connection() as conn:
        return [_row_to_dict(r) for r in conn.execute(query, params + (limit,)).fetchall()]


def booked_slots(asesor: str) -> set[str]:
    """Franjas (slot_iso) ya ocupadas por citas activas de ese asesor."""
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT slot_iso FROM appointments WHERE asesor = ? AND status IN ({placeholders})",
            (asesor, *ACTIVE_STATUSES),
        ).fetchall()
        return {r["slot_iso"] for r in rows}


def update_status(appointment_id: int, status: str):
    if status not in STATUSES:
        raise ValueError(f"Estado inválido: {status}")
    with get_connection() as conn:
        conn.execute(
            "UPDATE appointments SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), appointment_id),
        )


def reschedule(appointment_id: int, slot_iso: str, slot_label: str, asesor: str):
    with get_connection() as conn:
        conn.execute(
            """UPDATE appointments SET slot_iso = ?, slot_label = ?, asesor = ?,
               status = 'reprogramada', updated_at = ? WHERE id = ?""",
            (slot_iso, slot_label, asesor, _now(), appointment_id),
        )


def update_email_status(appointment_id: int, status: str):
    with get_connection() as conn:
        conn.execute("UPDATE appointments SET email_status = ? WHERE id = ?", (status, appointment_id))


def update_call_status(appointment_id: int, status: str):
    with get_connection() as conn:
        conn.execute("UPDATE appointments SET call_status = ? WHERE id = ?", (status, appointment_id))


def save_call_result(appointment_id: int, status: str, transcript: str | None, summary: str | None):
    with get_connection() as conn:
        conn.execute(
            "UPDATE appointments SET call_status = ?, call_transcript = ?, call_summary = ? WHERE id = ?",
            (status, transcript, summary, appointment_id),
        )


# ------------------------------------------------- preguntas sin respuesta

def log_unanswered(question: str):
    """Registra preguntas que el agente no pudo responder: es la lista de lo que falta
    agregar al documento de la Universidad."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO unanswered_questions (question, created_at) VALUES (?, ?)",
            (question.strip()[:500], _now()),
        )


def list_unanswered(limit: int = 200) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT question, COUNT(*) AS veces, MAX(created_at) AS ultima "
            "FROM unanswered_questions GROUP BY lower(question) ORDER BY veces DESC, ultima DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
