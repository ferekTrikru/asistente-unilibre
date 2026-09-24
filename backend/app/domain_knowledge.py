import json
import os
import re

from . import config

_DOMAIN_KNOWLEDGE_PATH = os.path.join(config.DATA_PATH, "..", "config", "domain_knowledge.json")
_DOMAIN_KNOWLEDGE_PATH = os.path.normpath(_DOMAIN_KNOWLEDGE_PATH)

_DEFAULT = {
    "general_context": "",
    "glossary": {},
    "relations": {},
}


def load_domain_knowledge() -> dict:
    try:
        with open(_DOMAIN_KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**_DEFAULT, **data}
    except Exception:
        return dict(_DEFAULT)


def inject_contextual_relations(query_text: str, domain_knowledge: dict) -> str:
    """Agrega aclaraciones contextuales cuando la pregunta menciona un término ambiguo."""
    relations = domain_knowledge.get("relations", {})
    injected = ""
    for term, relation_text in relations.items():
        if term.lower() in query_text.lower():
            injected += f"Contexto: {relation_text}\n\n"
    return injected


def expand_acronyms(text: str, domain_knowledge: dict) -> str:
    """Expande siglas institucionales usando el glosario (ej. 'ICFES' -> 'ICFES (Examen...)')."""
    glossary = domain_knowledge.get("glossary", {})
    if not glossary:
        return text

    expanded_text = text
    found_acronyms = set(re.findall(r"\b([A-Z]{2,6})\b", text))

    for acronym in found_acronyms:
        # Si el texto ya trae la sigla explicada entre paréntesis, no se vuelve a expandir.
        if acronym in glossary and not re.search(r"\b" + acronym + r"\b\s*\(", expanded_text):
            expanded_text = re.sub(
                r"\b" + acronym + r"\b",
                f"{acronym} ({glossary[acronym]})",
                expanded_text,
                count=1,
            )
    return expanded_text
