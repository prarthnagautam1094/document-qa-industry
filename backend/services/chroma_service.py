"""ChromaDB client setup and connection management.

Exposes get_embeddings() and get_vectordb() as FastAPI dependency
providers (via Depends(...) in the routers). Both are process-wide
singletons cached with lru_cache: the embedding model is expensive to
load and the Chroma store manages its own on-disk persistence, so
re-constructing either one per request would add unnecessary latency
without any benefit — there's nothing request-scoped about them.
"""

import logging
from functools import lru_cache

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Load and cache the sentence-transformer embedding model.

    Returns the same instance on every call after the first.
    """
    logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
    return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_vectordb() -> Chroma:
    """Return the process-wide Chroma vector store, creating it if needed.

    cosine similarity space is required for
    similarity_search_with_relevance_scores to return scores bounded to
    [0, 1] — Chroma's default L2 distance produces unbounded (often
    negative) scores that a fixed threshold can't sensibly filter against.
    Passing this constructor a persist_directory that already has data
    reopens the existing collection; an empty/missing directory starts a
    fresh one — either way this call is safe to make unconditionally.
    """
    logger.info("Opening Chroma vector store at %s", settings.PERSIST_DIRECTORY)
    return Chroma(
        persist_directory=settings.PERSIST_DIRECTORY,
        embedding_function=get_embeddings(),
        collection_metadata={"hnsw:space": "cosine"},
    )
