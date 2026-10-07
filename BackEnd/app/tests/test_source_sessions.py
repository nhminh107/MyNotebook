"""Exercise HTTP authentication and trace gating without live services."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
import pytest

from BackEnd.app.api import auth, document
from BackEnd.app.retrieval_models import PipelineEvent
from BackEnd.app.service.session_service import SESSION_COOKIE, session_secret


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("NOTEBOOK_SESSION_SECRET", "test-only-secret-with-at-least-32-characters")
    session_secret.cache_clear()
    monkeypatch.setattr(auth, "auth_service", SimpleNamespace(
        login=lambda _: {"user_id": "user-1", "user_name": "Minh", "plan": "Pro"},
        register=lambda _: {"user_id": "user-1", "user_name": "Minh", "plan": "Free"},
    ))
    monkeypatch.setattr(document, "get_database", lambda: SimpleNamespace(select_chat_histories_by_user=lambda _: []))
    monkeypatch.setattr(document, "get_pipeline", lambda: SimpleNamespace(query_events=lambda *args, **kwargs: iter([
        PipelineEvent(event="sources", payload={"turn_id": "turn-1", "sources": []}),
        PipelineEvent(event="token", payload={"content": "Answer"}),
        PipelineEvent(event="citations", payload={"saved": True, "cited_source_ids": []}),
    ])))
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(document.router)
    with TestClient(app) as test_client:
        yield test_client
    session_secret.cache_clear()


def login(client):
    result = client.post("/auth/login", json={"user_name": "Minh", "password": "password"})
    assert result.status_code == 200
    return result


def test_signed_session_is_httponly_and_bound_to_user(client) -> None:
    assert client.get("/documents/chats/user-1").status_code == 401
    response = login(client)
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert client.get("/documents/chats/user-1").status_code == 200
    assert client.get("/documents/chats/user-2").status_code == 403
    response = client.post("/documents/retrieval/stream", json={
        "user_id": "user-2", "chat_id": "chat-1", "user_query": "question", "include_sources": True,
    })
    assert response.status_code == 403
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/documents/chats/user-1").status_code == 401


def test_forged_or_expired_session_is_rejected(client) -> None:
    for token in ["forged", jwt.encode({"sub": "user-1", "exp": 1, "aud": "notebook", "iss": "notebook"}, session_secret(), algorithm="HS256")]:
        client.cookies.set(SESSION_COOKIE, token)
        assert client.get("/documents/chats/user-1").status_code == 401


def test_source_stream_and_trace_require_separate_authorization(client, monkeypatch) -> None:
    login(client)
    request = {"user_id": "user-1", "chat_id": "chat-1", "user_query": "question", "include_sources": True}
    response = client.post("/documents/retrieval/stream", json=request)
    assert response.status_code == 200
    assert "event: sources" in response.text and "event: done" in response.text
    assert "retrieval_trace" not in response.text
    request["include_trace"] = True
    monkeypatch.setenv("NOTEBOOK_RETRIEVAL_TRACE_KEY", "test-trace-key")
    assert client.post("/documents/retrieval/stream", json=request).status_code == 403
    assert client.post("/documents/retrieval/stream", json=request, headers={"X-Retrieval-Trace-Key": "wrong"}).status_code == 403
    assert client.post("/documents/retrieval/stream", json=request, headers={"X-Retrieval-Trace-Key": "test-trace-key"}).status_code == 200


def test_upload_cannot_impersonate_another_user(client) -> None:
    login(client)
    response = client.post(
        "/documents/upload",
        data={"user_id": "user-2", "chat_id": "chat-1"},
        files={"file": ("notes.txt", b"Evidence", "text/plain")},
    )
    assert response.status_code == 403


def test_agent_trace_is_rejected_instead_of_silently_ignored(client) -> None:
    login(client)
    response = client.post("/documents/retrieval/agent-stream", json={
        "user_id": "user-1", "chat_id": "chat-1", "user_query": "question",
        "include_sources": True, "include_trace": True,
    })
    assert response.status_code == 400
