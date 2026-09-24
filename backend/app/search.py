import re

TABULAR_QUERY_TERMS = [
    "semana", "fecha", "día", "cronograma", "schedule", "horario",
    "frecuencia", "cuota", "valor", "costo", "precio", "tiempo",
    "plazo", "tabla", "cuadro", "convocatoria", "cuándo", "when",
]

CONCEPTUAL_QUERY_TERMS = [
    "qué es", "define", "objetivo", "propósito", "criterio", "criterios",
    "requisito", "requisitos", "condiciones", "elegible", "selección",
    "duración", "modalidad", "proceso", "procedimiento", "descripción",
    "explica", "resumen", "por qué",
]


def detect_content_type(text: str) -> str:
    """Detecta si un fragmento es tabla, cronograma o texto corrido."""
    text_lower = text.lower()

    has_pipes = text.count("|") > 5
    has_dashes = "---" in text or "___" in text
    has_columns = bool(re.search(r"\s{3,}", text))

    if has_pipes or (has_dashes and has_columns):
        return "table"

    if re.search(r"(semana\s*\d+|fecha\s*límite|plazo)", text_lower):
        return "schedule"

    return "text"


def enrich_metadata(chunks):
    """Agrega metadatos de tipo de contenido a cada fragmento."""
    for i, chunk in enumerate(chunks):
        chunk.metadata["content_type"] = detect_content_type(chunk.page_content)
        chunk.metadata["chunk_index"] = i
    return chunks


def detect_query_type(query_text: str) -> str:
    query_lower = query_text.lower()
    tabular_count = sum(1 for term in TABULAR_QUERY_TERMS if term in query_lower)
    conceptual_count = sum(1 for term in CONCEPTUAL_QUERY_TERMS if term in query_lower)

    if tabular_count > conceptual_count and tabular_count > 0:
        return "tabular"
    if conceptual_count > 0:
        return "conceptual"
    return "general"


MAX_RESULTS = 5


def smart_search(query_text: str, vector_store):
    """Búsqueda adaptativa: ajusta k/threshold y prioriza tablas u horarios según la pregunta.
    Devuelve pocos fragmentos (los más relevantes) para que la respuesta final sea corta y citable."""
    query_type = detect_query_type(query_text)

    if query_type == "conceptual":
        k, threshold = 10, 0.3
    elif query_type == "tabular":
        k, threshold = 12, 0.2
    else:
        k, threshold = 10, 0.25

    results = vector_store.similarity_search_with_relevance_scores(
        query_text, k=k, score_threshold=threshold
    )

    if not results:
        return []

    boosted = []
    for doc, score in results:
        content_type = doc.metadata.get("content_type", "text")
        final_score = score

        if query_type == "tabular" and content_type in ("table", "schedule"):
            final_score += 0.2
        elif query_type == "conceptual" and content_type in ("table", "schedule"):
            final_score -= 0.1

        boosted.append((doc, final_score))

    boosted.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in boosted[:MAX_RESULTS]]
