"""Centralized application configuration, loaded once from the environment.

Run uvicorn with this directory (backend/) as the working directory
(e.g. `uvicorn main:app` from inside backend/) — load_dotenv() searches
upward from the current working directory for a .env file, and the
relative paths below (PERSIST_DIRECTORY) are resolved the same way.
"""

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Typed, centralized settings so every module reads config from one place
    instead of scattering os.getenv() calls and magic numbers throughout the
    codebase.
    """

    # Groq: required for query rewriting and answer generation. Left empty
    # (rather than raising at import time) so the app can still start and
    # serve /health and /docs without a key configured yet.
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # Postgres (Supabase-hosted) connection string for document/conversation/
    # query-log persistence. Left empty (rather than raising at import time)
    # for the same reason as GROQ_API_KEY: /health and /docs should still
    # come up even if this is misconfigured — see database.py's init_db()
    # for how a bad/missing value is handled at startup.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Supabase project URL and anon (public) API key, used only to verify
    # end-user JWTs on incoming requests (see services/auth_service.py) —
    # not for database access, which still goes through DATABASE_URL/
    # SQLAlchemy above. Left empty (rather than raising at import time)
    # for the same reason as GROQ_API_KEY/DATABASE_URL: every protected
    # route will 401 until these are configured, but /health and /docs
    # still come up.
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")

    # Chroma persists to disk here; relative to the process's working
    # directory, independent of the original Streamlit prototype's own
    # ./chroma_db so the two don't collide.
    PERSIST_DIRECTORY: str = os.getenv("PERSIST_DIRECTORY", "./chroma_db")

    # Embedding + LLM models, pinned to the values already validated in the
    # reference Streamlit implementation.
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    LLM_MODEL: str = "llama-3.3-70b-versatile"

    # Stage-2 re-ranking model (see rag_service.retrieve_relevant_chunks for
    # the full bi-encoder vs cross-encoder rationale). ms-marco-MiniLM-L-6-v2
    # is a small, fast cross-encoder trained specifically for passage
    # re-ranking, which is exactly this job.
    CROSS_ENCODER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Chunking, matching the reference implementation.
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # Retrieval: pull this many scored candidates from Chroma (stage 1,
    # bi-encoder), keep only the ones at or above RELEVANCE_THRESHOLD, then
    # cross-encoder re-rank the survivors (stage 2) and cap the context sent
    # to the LLM at MAX_CONTEXT_CHUNKS. MAX_RETRIEVAL_CANDIDATES was widened
    # from 5 to 10 specifically to give stage 2 a meaningful shortlist to
    # re-rank — with only 5 candidates surviving the threshold, re-ranking
    # has little room to change anything.
    # 0.2 was tuned empirically for all-MiniLM-L6-v2 in the reference app:
    # this embedding model produces low cosine similarity scores for short/
    # general questions matched against longer paragraph chunks even when
    # the chunk is genuinely the right answer, so a stricter threshold like
    # 0.5 rejected correct matches, not just off-topic ones.
    RELEVANCE_THRESHOLD: float = 0.2
    MAX_RETRIEVAL_CANDIDATES: int = 10
    MAX_CONTEXT_CHUNKS: int = 3


settings = Settings()
