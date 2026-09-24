import os

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


def answer_question(question: str, embeddings, qdrant_client) -> dict:
    existing = [c.name for c in qdrant_client.get_collections().collections]
    if config.COLLECTION_NAME not in existing:
        return {
            "answer": "Todavía no hay documentos cargados en la base de conocimiento. "
                      "Ejecuta el script de ingesta (backend/ingest.py) primero.",
            "sources": [],
        }

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
        }

    domain_knowledge = load_domain_knowledge()
    context, sources = _build_context(docs, domain_knowledge, question)

    prompt = create_prompt(context, question)
    response = llm.generate(prompt)
    response = expand_acronyms(response, domain_knowledge)

    if not response:
        return {"answer": "No se generó una respuesta a partir del contexto disponible.", "sources": []}

    if NOT_FOUND_MESSAGE in response:
        return {"answer": NOT_FOUND_MESSAGE, "sources": []}

    return {"answer": response, "sources": sources}
