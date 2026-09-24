"""Persistencia mínima de citas en SQLite (sin ORM: suficiente para el volumen de un
demo — una sola tabla, sin migraciones)."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

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
"""


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
    """Agrega columnas nuevas a una base ya existente (creada por una versión anterior
    de este proyecto) sin borrar los datos que ya tenga."""
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(appointments)")}
    for column in ("call_transcript", "call_summary"):
        if column not in existing_cols:
            conn.execute(f"ALTER TABLE appointments ADD COLUMN {column} TEXT")


def init_db():
    with get_connection() as conn:
        conn.execute(_SCHEMA)
        _migrate(conn)


def insert_appointment(data: dict) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO appointments
                (tipo, modalidad, slot_label, slot_iso, asesor, programa, sede,
                 necesidad, nombre, email, telefono, email_status, call_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'not_scheduled', ?)
            """,
            (
                data["tipo"],
                data["modalidad"],
                data["slot_label"],
                data["slot_iso"],
                data["asesor"],
                data.get("programa"),
                data.get("sede"),
                data.get("necesidad"),
                data.get("nombre"),
                data["email"],
                data.get("telefono"),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return cursor.lastrowid


def update_email_status(appointment_id: int, status: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE appointments SET email_status = ? WHERE id = ?",
            (status, appointment_id),
        )


def update_call_status(appointment_id: int, status: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE appointments SET call_status = ? WHERE id = ?",
            (status, appointment_id),
        )


def save_call_result(appointment_id: int, status: str, transcript: str | None, summary: str | None):
    with get_connection() as conn:
        conn.execute(
            "UPDATE appointments SET call_status = ?, call_transcript = ?, call_summary = ? WHERE id = ?",
            (status, transcript, summary, appointment_id),
        )


def get_appointment(appointment_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
        return dict(row) if row else None
