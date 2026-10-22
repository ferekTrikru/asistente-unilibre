import os
import re
from collections import OrderedDict
from datetime import datetime

from langchain_qdrant import QdrantVectorStore

from . import config, db, llm
from .agenda import BOGOTA
from .domain_knowledge import expand_acronyms, inject_contextual_relations, load_domain_knowledge
from .prompts import create_prompt
from .search import smart_search

MAX_CONTEXT_CHARS = 5500
NOT_FOUND_MESSAGE = "No encuentro esa información en los documentos disponibles."
NO_DOCS_MESSAGE = "No encuentro información sobre eso en los documentos disponibles."
# El modelo no siempre usa la frase exacta: "Lo siento, no encuentro información sobre...",
# "No hay información sobre..." también significan que el documento no tiene el dato.
_NOT_FOUND_RE = re.compile(
    r"(no encuentro|no tengo|no hay|no dispongo de|no cuento con)[^.]{0,80}informaci",
    re.IGNORECASE,
)
# Solo se mira el arranque de la respuesta: una respuesta útil puede mencionar más
# adelante que "no hay información" de un detalle secundario.
_NOT_FOUND_WINDOW = 160
# Una pregunta de pocas palabras suele ser de seguimiento ("¿y de noche?"): se busca
# junto con la pregunta anterior del aspirante para encontrar los fragmentos correctos.
FOLLOW_UP_MAX_WORDS = 8
HISTORY_TURNS = 4

_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre"]


def _today_label() -> str:
    today = datetime.now(BOGOTA)
    return f"{today.day} de {_MONTHS[today.month - 1]} de {today.year}"


def _format_source(doc) -> str:
    """Convierte metadata cruda (ruta de archivo + índice de página 0-based) en una
    etiqueta legible para el usuario, ej. 'Guia Institucional (p. 20)'."""
    source = doc.metadata.get("source", "documento")
    name = os.path.splitext(os.path.basename(source))[0].replace("_", " ").replace("-", " ").strip()
    page = doc.metadata.get("page")
    if isinstance(page, int):
        return f"{name} (p. {page + 1})"
    return name


def _build_context(docs, domain_knowledge: dict, query_text: str) -> tuple[str, list[str]]:
    context_parts = []
    sources = []
    total_chars = 0

    for doc in docs:
        content = doc.page_content
        if total_chars + len(content) > MAX_CONTEXT_CHARS:
            break

        context_parts.append(content)
        total_chars += len(content)

        label = _format_source(doc)
        if label not in sources:
            sources.append(label)

    context = "\n\n---\n\n".join(context_parts)

    relations = inject_contextual_relations(query_text, domain_knowledge)
    if relations:
        context = relations + "\n---\n\n" + context

    general_context = domain_knowledge.get("general_context", "")
    if general_context and len(docs) < 5:
        context = f"Contexto general:\n{general_context}\n\n---\n\n{context}"

    # Ficha oficial y compacta de la oferta: va siempre primero. Los datos de los 11
    # programas están repartidos en muchos fragmentos y el modelo los mezclaba
    # (fechas de Medicina para Bacteriología, "sí hay Psicología", títulos inventados).
    official = domain_knowledge.get("official_facts", "")
    if official:
        context = f"{official}\n\n---\n\n{context}"

    context = expand_acronyms(context, domain_knowledge)

    return context, sources


def _clean_history(history) -> list[dict]:
    """Deja solo los últimos turnos válidos ({role: user|bot, text}) y recorta su largo."""
    turns = []
    for item in (history or [])[-HISTORY_TURNS:]:
        role = item.get("role") if isinstance(item, dict) else None
        text = (item.get("text") or "").strip() if isinstance(item, dict) else ""
        if role in ("user", "bot") and text:
            turns.append({"role": role, "text": text[:400]})
    return turns


def _search_query(question: str, history: list[dict]) -> str:
    previous_user = next((t["text"] for t in reversed(history) if t["role"] == "user"), "")
    if previous_user and len(question.split()) <= FOLLOW_UP_MAX_WORDS:
        return f"{previous_user} {question}"
    return question


def _history_text(history: list[dict]) -> str:
    return "\n".join(("Aspirante: " if t["role"] == "user" else "Asistente: ") + t["text"] for t in history)


# ------------------------------------------------------------------ caché

_CACHE_MAX = 256
_answer_cache: "OrderedDict[str, dict]" = OrderedDict()


def _cache_key(question: str) -> str:
    """Normaliza la pregunta para que variaciones triviales (mayúsculas, espacios,
    signos de interrogación) compartan la misma respuesta en caché."""
    return " ".join(question.lower().strip(" ¿?¡!.").split())


def _cache_get(question: str):
    key = _cache_key(question)
    if key in _answer_cache:
        _answer_cache.move_to_end(key)
        return _answer_cache[key]
    return None


def _cache_put(question: str, result: dict) -> None:
    key = _cache_key(question)
    _answer_cache[key] = result
    _answer_cache.move_to_end(key)
    while len(_answer_cache) > _CACHE_MAX:
        _answer_cache.popitem(last=False)


# ------------------------------------------------------------- respuesta

def _log_unanswered(question: str) -> None:
    try:
        db.log_unanswered(question)
    except Exception:  # el registro nunca debe impedir responder
        pass


def _prepare(question: str, history: list[dict], embeddings, qdrant_client):
    """Busca los fragmentos y arma el prompt. Devuelve (resultado_final, None) si no hace
    falta llamar al modelo, o (None, (prompt, sources, domain_knowledge))."""
    existing = [c.name for c in qdrant_client.get_collections().collections]
    if config.COLLECTION_NAME not in existing:
        return {
            "answer": "Todavía no hay documentos cargados en la base de conocimiento. "
                      "Ejecuta el script de ingesta (backend/ingest.py) primero.",
            "sources": [],
        }, None

    vector_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=config.COLLECTION_NAME,
        embedding=embeddings,
    )

    query = _search_query(question, history)
    docs = smart_search(query, vector_store)
    if not docs:
        _log_unanswered(question)
        return {"answer": NO_DOCS_MESSAGE, "sources": []}, None

    domain_knowledge = load_domain_knowledge()
    context, sources = _build_context(docs, domain_knowledge, query)
    prompt = create_prompt(context, question, _history_text(history), _today_label())
    return None, (prompt, sources, domain_knowledge)


def _finalize(question: str, response: str, sources: list[str], domain_knowledge: dict) -> dict:
    response = expand_acronyms(response.strip(), domain_knowledge)
    if not response:
        return {"answer": "No se generó una respuesta a partir del contexto disponible.", "sources": []}
    if NOT_FOUND_MESSAGE in response or _NOT_FOUND_RE.search(response[:_NOT_FOUND_WINDOW]):
        _log_unanswered(question)
        return {"answer": NOT_FOUND_MESSAGE, "sources": []}
    return {"answer": response, "sources": sources}


def answer_question(question: str, embeddings, qdrant_client, history=None) -> dict:
    history = _clean_history(history)
    # La caché solo aplica a preguntas sin conversación previa: con historial, la misma
    # frase ("¿y de noche?") significa cosas distintas.
    if not history:
        cached = _cache_get(question)
        if cached:
            return cached

    early, prepared = _prepare(question, history, embeddings, qdrant_client)
    if early:
        return early

    prompt, sources, domain_knowledge = prepared
    result = _finalize(question, llm.generate(prompt), sources, domain_knowledge)
    if not history:
        _cache_put(question, result)
    return result


def answer_question_stream(question: str, embeddings, qdrant_client, history=None):
    """Versión en streaming de answer_question: emite eventos
    {"type": "token", "text": ...} mientras el modelo escribe, y al final
    {"type": "done", "answer": ..., "sources": [...]} con la respuesta ya procesada
    (siglas expandidas, detección de "no encuentro")."""
    history = _clean_history(history)
    if not history:
        cached = _cache_get(question)
        if cached:
            yield {"type": "done", **cached}
            return

    early, prepared = _prepare(question, history, embeddings, qdrant_client)
    if early:
        yield {"type": "done", **early}
        return

    prompt, sources, domain_knowledge = prepared
    text = ""
    for piece in llm.generate_stream(prompt):
        text += piece
        yield {"type": "token", "text": piece}

    result = _finalize(question, text, sources, domain_knowledge)
    if not history:
        _cache_put(question, result)
    yield {"type": "done", **result}
