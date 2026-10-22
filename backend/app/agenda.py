"""Agenda de asesores: calcula franjas libres reales a partir del horario de atención
(config/advisors.json) y de las citas activas guardadas en la base."""
import json
import os
from datetime import datetime, timedelta, timezone

from . import config, db

# Colombia no tiene horario de verano: UTC-5 fijo.
BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")
_WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre"]


def load_agenda() -> dict:
    path = config.ADVISORS_PATH
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(__file__), "..", path)
    with open(os.path.normpath(path), "r", encoding="utf-8") as f:
        return json.load(f)


def format_slot(dt: datetime) -> str:
    """'lunes 26 de octubre a las 10:30 a. m.' (mismo formato que muestra el chat)."""
    dt = dt.astimezone(BOGOTA)
    hour12 = dt.hour % 12 or 12
    ampm = "p. m." if dt.hour >= 12 else "a. m."
    return f"{_WEEKDAYS[dt.weekday()]} {dt.day} de {_MONTHS[dt.month - 1]} a las {hour12}:{dt.minute:02d} {ampm}"


def _advisors_for(agenda: dict, tipo: str) -> list[str]:
    names = [a["nombre"] for a in agenda["asesores"] if tipo in a.get("tipos", [])]
    return names or [a["nombre"] for a in agenda["asesores"]]


def _candidate_times(agenda: dict, now: datetime):
    start = now + timedelta(hours=agenda.get("anticipacion_minima_horas", 2))
    for day_offset in range(agenda.get("dias_hacia_adelante", 14) + 1):
        day = (now + timedelta(days=day_offset)).date()
        if day.weekday() not in agenda.get("dias_habiles", [0, 1, 2, 3, 4]):
            continue
        for hhmm in agenda["franjas"]:
            hour, minute = (int(x) for x in hhmm.split(":"))
            slot = datetime(day.year, day.month, day.day, hour, minute, tzinfo=BOGOTA)
            if slot >= start:
                yield slot


def available_slots(tipo: str, limit: int = 3, now: datetime | None = None) -> list[dict]:
    """Próximas franjas libres para ese tipo de atención. Reparte las opciones en días
    distintos cuando se puede, para que el aspirante tenga alternativas reales."""
    agenda = load_agenda()
    now = (now or datetime.now(BOGOTA)).astimezone(BOGOTA)
    advisors = _advisors_for(agenda, tipo)
    booked = {name: db.booked_slots(name) for name in advisors}

    free, days_used = [], set()
    fallback = []
    for slot in _candidate_times(agenda, now):
        iso = slot.isoformat()
        advisor = next((a for a in advisors if iso not in booked[a]), None)
        if not advisor:
            continue
        item = {"iso": iso, "label": format_slot(slot), "asesor": advisor}
        if slot.date() not in days_used:
            free.append(item)
            days_used.add(slot.date())
        else:
            fallback.append(item)
        if len(free) >= limit:
            break
    return (free + fallback)[:limit]


def is_slot_free(slot_iso: str, asesor: str) -> bool:
    return slot_iso not in db.booked_slots(asesor)


def parse_slot(slot_iso: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(slot_iso)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=BOGOTA)
