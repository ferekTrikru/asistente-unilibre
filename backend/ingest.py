"""
Carga los documentos institucionales de data/ (PDF, Word .docx, Markdown o texto) hacia Qdrant.

Uso:
    python ingest.py            # agrega/actualiza documentos
    python ingest.py --reset    # borra la colección y la reconstruye desde cero
"""

import argparse
import bisect
import glob
import os
import re
import zipfile
from xml.etree import ElementTree

from langchain_community.document_loaders import PyMuPDFLoader, TextLoader
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from qdrant_client import models

from app import config
from app.embeddings import get_embedding_function, get_qdrant_client
from app.search import enrich_metadata


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DOCX_HEADINGS = {"Heading1": "#", "Heading2": "##", "Heading3": "###"}


def _load_docx(path):
    """Convierte un .docx a Markdown sin dependencias extra: los estilos Título 1/2/3 pasan
    a #/##/### (para dividir por secciones), las viñetas a guiones y las tablas a filas."""
    body = ElementTree.fromstring(zipfile.ZipFile(path).read("word/document.xml")).find(_W + "body")

    def text_of(node):
        return "".join(t.text or "" for t in node.iter(_W + "t")).strip()

    lines = []
    for element in body:
        if element.tag == _W + "p":
            text = text_of(element)
            if not text:
                continue
            style = element.find(f"{_W}pPr/{_W}pStyle")
            style = style.get(_W + "val") if style is not None else ""
            if style in _DOCX_HEADINGS:
                lines += ["", f"{_DOCX_HEADINGS[style]} {text}"]
            elif element.find(f"{_W}pPr/{_W}numPr") is not None:
                lines.append(f"- {text}")
            else:
                lines += ["", text]
        elif element.tag == _W + "tbl":
            lines.append("")
            for row in element.iter(_W + "tr"):
                lines.append("| " + " | ".join(text_of(cell) for cell in row.findall(_W + "tc")) + " |")
    return Document(page_content="\n".join(lines).strip(), metadata={"source": path})


_PAGE_NOISE = re.compile(r"^\s*(P[aá]gina\s+\d+|\d{1,3})\s*$", re.MULTILINE)


def _load_pdf(path):
    """Une todas las páginas del PDF en un solo documento: si se cargan por página, una
    sección que cruza el salto de página (ej. un calendario) queda partida y el fragmento
    pierde el título que dice de qué programa habla. Se guarda dónde empieza cada página
    para poder citar la página de cada fragmento."""
    pages = PyMuPDFLoader(path).load()
    text, page_starts = "", []
    for page in pages:
        page_starts.append(len(text))
        text += _PAGE_NOISE.sub("", page.page_content).strip() + "\n\n"
    return Document(page_content=text.strip(), metadata={"source": path, "page_starts": page_starts})


def load_documents():
    documents = []
    for pdf_path in sorted(glob.glob(os.path.join(config.DATA_PATH, "*.pdf"))):
        documents.append(_load_pdf(pdf_path))
    for docx_path in sorted(glob.glob(os.path.join(config.DATA_PATH, "*.docx"))):
        if not os.path.basename(docx_path).startswith("~$"):  # archivos temporales de Word
            documents.append(_load_docx(docx_path))
    for pattern in ("*.md", "*.txt"):
        for text_path in sorted(glob.glob(os.path.join(config.DATA_PATH, pattern))):
            documents.extend(TextLoader(text_path, encoding="utf-8").load())
    return documents


def _split_markdown(doc):
    """Divide un .md por títulos: cada sección queda en su propio fragmento y lleva su ruta
    de títulos al inicio, para que la búsqueda sepa de qué tema habla."""
    headers = [("#", "h1"), ("##", "h2"), ("###", "h3")]
    sections = MarkdownHeaderTextSplitter(headers_to_split_on=headers).split_text(doc.page_content)
    out = []
    for section in sections:
        path = " > ".join(section.metadata[h] for h in ("h1", "h2", "h3") if h in section.metadata)
        content = f"{path}\n\n{section.page_content}" if path else section.page_content
        out.append(Document(page_content=content, metadata=dict(doc.metadata)))
    return out


def split_documents(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    prepared = []
    for doc in documents:
        if doc.metadata.get("source", "").lower().endswith((".md", ".docx")):
            prepared.extend(_split_markdown(doc))
        else:
            prepared.append(doc)
    chunks = []
    for doc in prepared:
        page_starts = doc.metadata.pop("page_starts", None)
        if page_starts is None:
            chunks.extend(splitter.split_documents([doc]))
            continue
        # PDF unido: cada fragmento se etiqueta con la página donde empieza.
        offset = 0
        for piece in splitter.split_text(doc.page_content):
            start = doc.page_content.find(piece[:200], offset)
            if start >= 0:
                offset = start + 1
            page = max(bisect.bisect_right(page_starts, max(start, 0)) - 1, 0)
            chunks.append(Document(page_content=piece, metadata={**doc.metadata, "page": page}))
    return enrich_metadata(chunks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Borra la colección antes de cargar")
    args = parser.parse_args()

    client = get_qdrant_client()
    embeddings = get_embedding_function()

    existing = [c.name for c in client.get_collections().collections]
    if args.reset and config.COLLECTION_NAME in existing:
        # Se vacían los puntos en vez de borrar la colección: en Qdrant local sobre Windows,
        # delete_collection no alcanza a borrar los archivos y los fragmentos viejos reaparecen.
        client.delete(
            collection_name=config.COLLECTION_NAME,
            points_selector=models.FilterSelector(filter=models.Filter()),
        )
        print(f"Colección '{config.COLLECTION_NAME}' vaciada.")

    if config.COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=config.COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=config.EMBEDDING_DIM, distance=models.Distance.COSINE
            ),
        )
        print(f"Colección '{config.COLLECTION_NAME}' creada.")

    documents = load_documents()
    if not documents:
        print(f"No se encontraron documentos (.pdf, .docx, .md, .txt) en '{config.DATA_PATH}'. Agrega archivos ahí y vuelve a correr este script.")
        return

    chunks = split_documents(documents)
    print(f"{len(documents)} documento(s) -> {len(chunks)} fragmento(s).")

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=config.COLLECTION_NAME,
        embedding=embeddings,
    )

    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        vector_store.add_documents(batch)
        print(f"Cargados {min(i + len(batch), len(chunks))}/{len(chunks)} fragmentos...")

    print("Listo.")


if __name__ == "__main__":
    main()
