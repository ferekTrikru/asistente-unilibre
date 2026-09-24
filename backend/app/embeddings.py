import os

from langchain_community.embeddings import HuggingFaceEmbeddings
from qdrant_client import QdrantClient

from . import config

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def get_embedding_function() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
    )


def get_qdrant_client() -> QdrantClient:
    if config.QDRANT_URL:
        return QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY or None)
    return QdrantClient(path=config.QDRANT_LOCAL_PATH, timeout=60.0)
