"""
Procesador de tablas genérico.
Funciones escalables para detectar, procesar e interpretar tablas
en cualquier documento (sin dependencias de un dominio específico).
"""

import re
from typing import List, Dict, Tuple


def detect_tabular_content(text: str) -> bool:
    """Detecta si un fragmento de texto contiene contenido tabular."""
    text_lower = text.lower()

    table_keywords = [
        "schedule of activities", "evaluaciones", "tabla", "visitas",
        "weeks", "semana", "cronograma", "actividades", "procedimientos",
        "mediciones", "medidas", "evaluación", "assessment", "timeline",
        "calendario", "programa", "horario", "itinerario"
    ]

    has_table_keyword = any(kw in text_lower for kw in table_keywords)
    has_pipes = text.count("|") > 3
    has_dashes = text.count("---") > 1
    has_multiple_spaces = len(re.findall(r"\s{4,}", text)) > 2

    return has_table_keyword or (has_pipes and has_dashes) or (has_multiple_spaces and has_table_keyword)


def flatten_table_row(row: List[str], header: List[str]) -> str:
    """Convierte una fila de tabla en una frase textual comprensible."""
    if not row or not header:
        return ""

    item_name = row[0].strip()
    if not item_name:
        return ""

    marked_columns = []
    for i, cell in enumerate(row[1:], 1):
        if i < len(header):
            cell_lower = cell.strip().lower()
            if cell_lower in ["x", "✓", "sí", "yes", "1", "true", "v", "•", "●"]:
                marked_columns.append(header[i].strip())

    if marked_columns:
        columns_str = ", ".join(marked_columns)
        return f"{item_name} | Aplica en: {columns_str}."

    return f"{item_name} | Sin marcar en la tabla."


def extract_table_structure(text: str) -> List[Tuple[str, List[str]]]:
    """Extrae estructura de tabla de texto con formato de tabla."""
    lines = text.split("\n")
    results = []

    table_lines = [l for l in lines if "|" in l or "\t" in l]
    if not table_lines:
        return results

    header_line = table_lines[0]
    header = re.split(r"\||\t", header_line)
    header = [h.strip() for h in header if h.strip()]

    for line in table_lines[1:]:
        if not line.strip() or "---" in line:
            continue

        cells = re.split(r"\||\t", line)
        cells = [c.strip() for c in cells]

        if cells and cells[0]:
            flattened = flatten_table_row(cells, header)
            if flattened:
                results.append((cells[0], flattened))

    return results


def infer_temporal_points(text: str) -> List[str]:
    """Extrae puntos temporales (semanas, días, meses) del texto."""
    patterns = [
        r"semana\s*(\d+)",
        r"week\s*(\d+)",
        r"día\s*(\d+)",
        r"day\s*(\d+)",
        r"mes\s*(\d+)",
        r"month\s*(\d+)",
    ]

    temporal_points = []
    for pattern in patterns:
        matches = re.findall(pattern, text.lower())
        temporal_points.extend(matches)

    unique_points = sorted(set(temporal_points), key=lambda x: int(x) if x.isdigit() else 0)
    return unique_points


def count_evaluations(text: str) -> Dict[str, int]:
    """Cuenta marcas/evaluaciones en el texto."""
    return {
        "total_marks": len(re.findall(r"[xX✓•●]", text)),
        "temporal_points": len(infer_temporal_points(text)),
        "rows": len([l for l in text.split("\n") if "|" in l or "\t" in l]),
    }


def generate_table_summary(text: str) -> str:
    """Genera un resumen textual de una tabla."""
    temporal_points = infer_temporal_points(text)
    counts = count_evaluations(text)

    summary_parts = []
    if temporal_points:
        summary_parts.append(f"Puntos temporales: {', '.join(temporal_points)}.")
    if counts["total_marks"] > 0:
        summary_parts.append(f"Total de marcas encontradas: {counts['total_marks']}.")
    if counts["rows"] > 0:
        summary_parts.append(f"Número de filas en la tabla: {counts['rows']}.")

    return " ".join(summary_parts) if summary_parts else "Tabla sin información clara."


def is_question_tabular(query: str) -> bool:
    """Detecta si una pregunta requiere información tabular/cronológica."""
    query_lower = query.lower()

    tabular_indicators = [
        "cuándo", "en qué", "cuántas", "cuáles", "frecuencia", "cronograma",
        "schedule", "timeline", "cuántos", "número de", "cantidad",
        "en qué momento", "en qué semana", "en qué fecha", "horario",
        "durante", "calendario", "convocatoria"
    ]

    return any(indicator in query_lower for indicator in tabular_indicators)


def enhance_context_with_table_info(context: str, query: str) -> str:
    """Enriquece el contexto con un resumen tabular si la pregunta lo requiere."""
    if not is_question_tabular(query):
        return context

    if detect_tabular_content(context):
        summary = generate_table_summary(context)
        return f"RESUMEN DE TABLA:\n{summary}\n\n---\n\n{context}"

    return context
