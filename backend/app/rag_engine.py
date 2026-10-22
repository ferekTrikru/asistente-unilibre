import os
from collections import OrderedDict

from langchain_qdrant import QdrantVectorStore

from . import config, llm
from .domain_knowledge import expand_acronyms, inject_contextual_relations, load_domain_knowledge
from .prompts import create_prompt
from .search import smart_search
from .table_processor import enhance_context_with_table_info, is_question_tabular

MAX_CONTEXT_CHARS = 8000
NOT_FOUND_MESSAGE = "No encuentro esa información en los documentos disponibles."


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

    if is_question_tabular(query_text):
        context = enhance_context_with_table_info(context, query_text)

    context = expand_acronyms(context, domain_knowledge)

    return context, sources


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
    _answer_cache[_cache_key(question)] = result
    _answer_cache.move_to_end(_cache_key(question))
    while len(_answer_cache) > _CACHE_MAX:
        _answer_cache.popitem(last=False)


def _prepare(question: str, embeddings, qdrant_client):
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

    docs = smart_search(question, vector_store)
    if not docs:
        return {
            "answer": "No encuentro información sobre eso en los documentos disponibles.",
            "sources": [],
        }, None

    domain_knowledge = load_domain_knowledge()
    context, sources = _build_context(docs, domain_knowledge, question)
    return None, (create_prompt(context, question), sources, domain_knowledge)


def _finalize(response: str, sources: list[str], domain_knowledge: dict) -> dict:
    response = expand_acronyms(response.strip(), domain_knowledge)
    if not response:
        return {"answer": "No se generó una respuesta a partir del contexto disponible.", "sources": []}
    if NOT_FOUND_MESSAGE in response:
        return {"answer": NOT_FOUND_MESSAGE, "sources": []}
    return {"answer": response, "sources": sources}


def answer_question(question: str, embeddings, qdrant_client) -> dict:
    cached = _cache_get(question)
    if cached:
        return cached

    early, prepared = _prepare(question, embeddings, qdrant_client)
    if early:
        return early

    prompt, sources, domain_knowledge = prepared
    result = _finalize(llm.generate(prompt), sources, domain_knowledge)
    _cache_put(question, result)
    return result


def answer_question_stream(question: str, embeddings, qdrant_client):
    """Versión en streaming de answer_question: emite eventos
    {"type": "token", "text": ...} mientras el modelo escribe, y al final
    {"type": "done", "answer": ..., "sources": [...]} con la respuesta ya procesada
    (siglas expandidas, detección de "no encuentro")."""
    cached = _cache_get(question)
    if cached:
        yield {"type": "done", **cached}
        return

    early, prepared = _prepare(question, embeddings, qdrant_client)
    if early:
        yield {"type": "done", **early}
        return

    prompt, sources, domain_knowledge = prepared
    text = ""
    for piece in llm.generate_stream(prompt):
        text += piece
        yield {"type": "token", "text": piece}

    result = _finalize(text, sources, domain_knowledge)
    _cache_put(question, result)
    yield {"type": "done", **result}
