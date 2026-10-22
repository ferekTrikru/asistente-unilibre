import re
import unicodedata

TABULAR_QUERY_TERMS = [
    "semana", "fecha", "día", "cronograma", "calendario", "horario",
    "frecuencia", "cuota", "valor", "costo", "precio", "tiempo",
    "plazo", "tabla", "cuadro", "convocatoria", "cuándo", "hasta cuándo",
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


MAX_RESULTS = 8
# Candidatos que trae la búsqueda semántica antes de reordenar con palabras clave.
CANDIDATES = 24
# Peso de las palabras clave frente al parecido semántico. El modelo de embeddings es
# pequeño y confunde fichas de programas parecidas; nombrar el programa ("Derecho",
# "Fisioterapia") debe pesar.
KEYWORD_WEIGHT = 0.25
HEADING_BONUS = 0.12

_STOPWORDS = {
    "cuanto", "cuanta", "cuantos", "cuantas", "cuesta", "cuestan", "valor", "tiene", "tienen",
    "puedo", "quiero", "saber", "sobre", "para", "esta", "estan", "como", "donde", "cuando",
    "hasta", "desde", "tengo", "hacer", "universidad", "libre", "barranquilla", "carrera",
    "programa", "estudiar", "necesito", "alguna", "algun", "ustedes", "seria", "favor",
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _keywords(query_text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", _normalize(query_text))
    return [w for w in words if len(w) >= 4 and w not in _STOPWORDS]


def _keyword_score(keywords: list[str], doc) -> tuple[float, float]:
    """(fracción de palabras clave presentes en el fragmento, bono si están en su título)."""
    if not keywords:
        return 0.0, 0.0
    text = _normalize(doc.page_content)
    heading = text.split("\n", 1)[0] if text.startswith("[") else ""
    present = [w for w in keywords if w in text]
    in_heading = any(w in heading for w in keywords)
    return len(present) / len(keywords), (HEADING_BONUS if in_heading else 0.0)


def smart_search(query_text: str, vector_store):
    """Búsqueda híbrida: trae candidatos por parecido semántico y los reordena sumando
    coincidencia de palabras clave (con bono si aparecen en el título de la sección del
    fragmento) y el tipo de contenido. Devuelve pocos fragmentos para que la respuesta
    sea corta y citable."""
    query_type = detect_query_type(query_text)
    threshold = {"conceptual": 0.3, "tabular": 0.2}.get(query_type, 0.25)

    results = vector_store.similarity_search_with_relevance_scores(query_text, k=CANDIDATES)
    # Si ni el mejor candidato supera el umbral, no hay nada relevante en los documentos.
    if not results or results[0][1] < threshold:
        return []

    keywords = _keywords(query_text)
    boosted = []
    for doc, score in results:
        content_type = doc.metadata.get("content_type", "text")
        coverage, heading_bonus = _keyword_score(keywords, doc)
        final_score = score + KEYWORD_WEIGHT * coverage + heading_bonus

        if query_type == "tabular" and content_type in ("table", "schedule"):
            final_score += 0.2
        elif query_type == "conceptual" and content_type in ("table", "schedule"):
            final_score -= 0.1

        boosted.append((doc, final_score))

    boosted.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in boosted[:MAX_RESULTS]]
