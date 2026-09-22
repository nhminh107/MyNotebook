import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from BackEnd.app.api import document as document_api


class StubPipeline:
    def __init__(self, result: str = "Grounded answer") -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def query(self, user_id: str, user_query: str) -> str:
        self.calls.append((user_id, user_query))
        return self.result


class StubUploadPipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str, bytes]] = []

    def insert_doc_pipeline(
        self,
        doc_path: str,
        user_id: str,
        chat_id: str,
        file_name: str,
    ) -> None:
        path = Path(doc_path)
        self.calls.append((path.suffix, user_id, chat_id, file_name, path.read_bytes()))


class StubUploadFile:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self.content = content

    async def read(self) -> bytes:
        return self.content


def test_stream_routes_are_registered() -> None:
    routes = {
        route.path: route.methods
        for route in document_api.router.routes
    }

    assert "/documents/retrieval" not in routes
    assert routes["/documents/retrieval/stream"] == {"POST"}
    assert routes["/documents/retrieval/agent-stream"] == {"POST"}
    assert routes["/documents/chats/{user_id}"] == {"GET"}
    assert routes["/documents/chats/{user_id}/{chat_id}"] == {"GET"}


def test_get_chat_histories_returns_user_chats(monkeypatch) -> None:
    class StubDatabase:
        def select_chat_histories_by_user(self, user_id: str):
            assert user_id == "user-001"
            return [{"chat_id": "chat-001", "conversation": []}]

    monkeypatch.setattr(document_api, "get_database", lambda: StubDatabase())

    response = document_api.get_chat_histories(" user-001 ")

    assert response == {
        "data": [{"chat_id": "chat-001", "conversation": []}]
    }


def test_get_chat_history_returns_only_chat_documents(monkeypatch) -> None:
    class StubDatabase:
        def select_chat_history(self, user_id: str, chat_id: str):
            assert (user_id, chat_id) == ("user-001", "chat-001")
            return {
                "chat_id": chat_id,
                "conversation": [{"user": "Hello", "chatbot": "Hi"}],
                "summary": "Greeting",
            }

        def select_document_by_chat(self, user_id: str, chat_id: str):
            assert (user_id, chat_id) == ("user-001", "chat-001")
            return [{
                "document_id": "doc-001",
                "chat_id": chat_id,
                "type": ".pdf",
                "file_name": "notes.pdf",
            }]

    monkeypatch.setattr(document_api, "get_database", lambda: StubDatabase())

    response = document_api.get_chat_history("user-001", "chat-001")

    assert response["data"]["chat"]["summary"] == "Greeting"
    assert response["data"]["documents"] == [
        {
            "document_id": "doc-001",
            "chat_id": "chat-001",
            "type": ".pdf",
            "file_name": "notes.pdf",
        }
    ]


def test_get_chat_history_returns_404_when_missing(monkeypatch) -> None:
    class StubDatabase:
        def select_chat_history(self, user_id: str, chat_id: str):
            return None

    monkeypatch.setattr(document_api, "get_database", lambda: StubDatabase())

    with pytest.raises(HTTPException) as error:
        document_api.get_chat_history("user-001", "missing-chat")

    assert error.value.status_code == 404


def test_retrieval_request_rejects_empty_query() -> None:
    with pytest.raises(ValidationError):
        document_api.RetrievalRequest(
            user_id="001",
            chat_id="chat-001",
            user_query="",
        )


def test_stream_retrieval_events_emits_tokens_and_done() -> None:
    class StreamingPipeline:
        def query_stream(self, user_id: str, user_query: str, chat_id: str):
            assert user_id == "001"
            assert user_query == "question"
            assert chat_id == "chat-001"
            yield "Hello"
            yield " **world**"

    events = list(
        document_api.stream_retrieval_events(
            pipeline=StreamingPipeline(),
            user_id="001",
            user_query="question",
            chat_id="chat-001",
        )
    )

    assert events == [
        'event: token\ndata: {"content": "Hello"}\n\n',
        'event: token\ndata: {"content": " **world**"}\n\n',
        "event: done\ndata: {}\n\n",
    ]


def test_stream_retrieval_events_uses_agent_pipeline_when_requested() -> None:
    class AgentStreamingPipeline:
        def agent_query_stream(
            self,
            user_id: str,
            user_query: str,
            chat_id: str,
        ):
            assert user_id == "001"
            assert user_query == "question"
            assert chat_id == "chat-001"
            yield "Agent answer"

        def query_stream(self, **kwargs):
            raise AssertionError("Standard retrieval must not be called")

    events = list(
        document_api.stream_retrieval_events(
            pipeline=AgentStreamingPipeline(),
            user_id="001",
            user_query="question",
            chat_id="chat-001",
            use_agent=True,
        )
    )

    assert events == [
        'event: token\ndata: {"content": "Agent answer"}\n\n',
        "event: done\ndata: {}\n\n",
    ]


def test_stream_retrieval_events_hides_backend_error() -> None:
    class FailingPipeline:
        def query_stream(self, user_id: str, user_query: str, chat_id: str):
            raise RuntimeError("private backend detail")
            yield

    events = list(
        document_api.stream_retrieval_events(
            pipeline=FailingPipeline(),
            user_id="001",
            user_query="question",
            chat_id="chat-001",
        )
    )

    assert events == [
        "event: error\n"
        'data: {"detail": "Unable to stream document information."}\n\n'
    ]


def test_upload_document_accepts_supported_extension(monkeypatch) -> None:
    pipeline = StubUploadPipeline()
    monkeypatch.setattr(document_api, "get_pipeline", lambda: pipeline)
    upload = StubUploadFile(filename="notes.txt", content=b"retrieval notes")

    response = asyncio.run(
        document_api.upload_document(user_id="user-001", chat_id="chat-001", file=upload)
    )

    assert response == {
        "message": "Document uploaded successfully.",
        "filename": "notes.txt",
        "user_id": "user-001",
        "chat_id": "chat-001",
    }
    assert pipeline.calls == [
        (".txt", "user-001", "chat-001", "notes.txt", b"retrieval notes")
    ]


def test_upload_document_rejects_unsupported_extension(monkeypatch) -> None:
    pipeline = StubUploadPipeline()
    monkeypatch.setattr(document_api, "get_pipeline", lambda: pipeline)
    upload = StubUploadFile(filename="notes.csv", content=b"unsupported")

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            document_api.upload_document(
                user_id="user-001",
                chat_id="chat-001",
                file=upload,
            )
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Unsupported file type: .csv"
    assert pipeline.calls == []
