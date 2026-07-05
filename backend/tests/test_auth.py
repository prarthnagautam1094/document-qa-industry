"""Covers get_current_user's 401 behavior directly.

conftest.py overrides get_current_user for every other test in this suite
(so ingestion/retrieval tests don't need a real Supabase project and a
real signed JWT) — that override would hide a broken auth dependency, so
these tests temporarily remove it to exercise the real dependency against
protected routes.
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from services import auth_service


@pytest.fixture
def unauthenticated_client():
    """A TestClient with the get_current_user override removed for the duration of the test."""
    original = app.dependency_overrides.pop(auth_service.get_current_user, None)
    with TestClient(app) as test_client:
        yield test_client
    if original is not None:
        app.dependency_overrides[auth_service.get_current_user] = original


def test_ask_without_token_returns_401(unauthenticated_client):
    response = unauthenticated_client.post(
        "/chat/ask",
        json={"question": "anything", "session_id": "s1", "conversation_history": []},
    )
    assert response.status_code == 401


def test_list_documents_without_token_returns_401(unauthenticated_client):
    response = unauthenticated_client.get("/documents/")
    assert response.status_code == 401


def test_ask_with_garbage_token_returns_401(unauthenticated_client):
    response = unauthenticated_client.post(
        "/chat/ask",
        json={"question": "anything", "session_id": "s1", "conversation_history": []},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_health_does_not_require_auth(unauthenticated_client):
    # /health is intentionally unauthenticated (load balancer liveness
    # checks can't sign a Supabase JWT) — confirms auth is scoped to the
    # protected routers, not applied globally.
    response = unauthenticated_client.get("/health")
    assert response.status_code == 200
