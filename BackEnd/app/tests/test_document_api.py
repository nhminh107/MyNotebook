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
        self.calls: list[tuple[str, str, bytes]] = []

    def insert_doc_pipeline(self, doc_path: str, user_id: str) -> None:
        path = Path(doc_path)
        self.calls.append((path.suffix, user_id, path.read_bytes()))


class StubUploadFile:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self.content = content

    async def read(self) -> bytes:
        return self.content


def test_retrieval_route_is_registered() -> None:
    routes = {
        route.path: route.methods
        for route in document_api.router.routes
    }

    assert routes["/documents/retrieval"] == {"POST"}
    assert routes["/documents/retrieval/stream"] == {"POST"}


def test_retrieve_document_returns_pipeline_result(monkeypatch) -> None:
    pipeline = StubPipeline()
    monkeypatch.setattr(document_api, "get_pipeline", lambda: pipeline)
    request = document_api.RetrievalRequest(
        user_id=" 001 ",
        user_query=" What is RAG? ",
    )

    response = document_api.retrieve_document(request)

    assert response == document_api.RetrievalResponse(
        message="Retrieval completed successfully.",
        data="Grounded answer",
    )
    assert pipeline.calls == [("001", "What is RAG?")]


def test_retrieve_document_rejects_blank_values(monkeypatch) -> None:
    pipeline = StubPipeline()
    monkeypatch.setattr(document_api, "get_pipeline", lambda: pipeline)
    request = document_api.RetrievalRequest(
        user_id="   ",
        user_query="question",
    )

    with pytest.raises(HTTPException) as error:
        document_api.retrieve_document(request)

    assert error.value.status_code == 400
    assert pipeline.calls == []


def test_retrieval_request_rejects_empty_query() -> None:
    with pytest.raises(ValidationError):
        document_api.RetrievalRequest(
            user_id="001",
            user_query="",
        )


def test_retrieve_document_hides_backend_error(monkeypatch) -> None:
    def raise_backend_error():
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr(document_api, "get_pipeline", raise_backend_error)
    request = document_api.RetrievalRequest(
        user_id="001",
        user_query="question",
    )

    with pytest.raises(HTTPException) as error:
        document_api.retrieve_document(request)

    assert error.value.status_code == 500
    assert error.value.detail == "Unable to retrieve document information."


def test_stream_retrieval_events_emits_tokens_and_done() -> None:
    class StreamingPipeline:
        def query_stream(self, user_id: str, user_query: str):
            assert user_id == "001"
            assert user_query == "question"
            yield "Hello"
            yield " **world**"

    events = list(
        document_api.stream_retrieval_events(
            pipeline=StreamingPipeline(),
            user_id="001",
            user_query="question",
        )
    )

    assert events == [
        'event: token\ndata: {"content": "Hello"}\n\n',
        'event: token\ndata: {"content": " **world**"}\n\n',
        "event: done\ndata: {}\n\n",
    ]


def test_stream_retrieval_events_hides_backend_error() -> None:
    class FailingPipeline:
        def query_stream(self, user_id: str, user_query: str):
            raise RuntimeError("private backend detail")
            yield

    events = list(
        document_api.stream_retrieval_events(
            pipeline=FailingPipeline(),
            user_id="001",
            user_query="question",
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
        document_api.upload_document(user_id="user-001", file=upload)
    )

    assert response == {
        "message": "Document uploaded successfully.",
        "filename": "notes.txt",
        "user_id": "user-001",
    }
    assert pipeline.calls == [(".txt", "user-001", b"retrieval notes")]


def test_upload_document_rejects_unsupported_extension(monkeypatch) -> None:
    pipeline = StubUploadPipeline()
    monkeypatch.setattr(document_api, "get_pipeline", lambda: pipeline)
    upload = StubUploadFile(filename="notes.csv", content=b"unsupported")

    with pytest.raises(HTTPException) as error:
        asyncio.run(document_api.upload_document(user_id="user-001", file=upload))

    assert error.value.status_code == 400
    assert error.value.detail == "Unsupported file type: .csv"
    assert pipeline.calls == []
