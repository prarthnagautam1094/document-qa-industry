"""Verifies Supabase-issued JWTs on incoming requests and exposes the
current user's id to route handlers.

Multi-tenancy matters here because this backend stores every user's
uploaded documents, chat history, and Chroma embeddings in the same
shared Postgres tables and the same shared vector collection — there is
no per-customer database or index. Without enforcing get_current_user()
on every protected route and filtering every query/Chroma operation by
the resulting user_id, one user's request could read or delete another
user's documents and conversations simply by knowing (or guessing) a
filename or session id. That's not a hypothetical edge case for a real
SaaS product — it's the difference between a working product and a data
breach the moment a second customer signs up, so isolation is enforced
at the data-access layer (routers + rag_service + database.py) rather
than trusted to the frontend.
"""

import logging
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from config import settings

logger = logging.getLogger(__name__)

# auto_error=False so a missing header raises our own 401 with a clear
# detail message below, instead of FastAPI's generic "Not authenticated".
_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Return the process-wide Supabase client, creating it on first use.

    Only ever used to verify tokens (auth.get_user), so the anon key is
    sufficient — this never touches Supabase's Postgres or storage APIs.
    """
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency: verify the bearer token and return the caller's user id.

    Raises 401 if the Authorization header is missing, malformed, or the
    token doesn't verify against Supabase (expired, forged, wrong
    project). Every protected route depends on this rather than trusting
    a user_id passed in the request body/query — that would let a caller
    simply claim to be any user.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token. Include 'Authorization: Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = get_supabase_client().auth.get_user(credentials.credentials)
    except Exception:
        logger.warning("Supabase token verification failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = response.user if response else None
    if user is None or not user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user.id
