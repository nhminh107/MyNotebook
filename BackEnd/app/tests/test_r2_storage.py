"""Original-document storage, ownership and citation-link regressions."""

from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from uuid import uuid4
from botocore.exceptions import ClientError, EndpointConnectionError

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
import numpy as np
import pytest

from BackEnd.app.api import document as document_api
from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.database.sql_models import Document
from BackEnd.app.doc_extractor import extractor
from BackEnd.app.pipeline import Pipeline
from BackEnd.app.retrieval_models import RetrievalHit, SourceRegistry
from BackEnd.app.service import r2_storage
from BackEnd.app.service.r2_storage import CloudflareR2, StorageError, iter_document_bytes
from BackEnd.app.service.session_service import SESSION_COOKIE, session_secret


@pytest.fixture
def storage(monkeypatch):
    monkeypatch.setenv("S3_API_KEY", "test-r2-token")
    monkeypatch.setenv("CF_ACC_ID", "test-account")
    monkeypatch.setenv("S3_API_URL", "https://test-account.r2.cloudflarestorage.com")
    return CloudflareR2()


def test_upload_preserves_bytes_and_returns_original_file_metadata(storage, tmp_path, monkeypatch):
    path = tmp_path / "Vietnamese notes.pdf"
    content = b"%PDF-1.4\nOriginal document bytes\n"
    path.write_bytes(content)
    document_id = str(uuid4())

    def put(**kwargs):
        assert kwargs["Bucket"] == "mynotebook"
        assert kwargs["Key"] == f"documents/{document_id}.pdf"
        assert kwargs["ContentType"] == "application/pdf"
        assert kwargs["ContentLength"] == len(content)
        assert kwargs["Body"].read() == content
        return {"ETag": "test-etag"}

    storage._client = SimpleNamespace(put_object=put)
    result = storage.upload_document(path, document_id)
    assert result["storage_bucket"] == "mynotebook"
    assert result["storage_key"] == f"documents/{document_id}.pdf"
    assert result["sha256"] == sha256(content).hexdigest()
    assert result["file_size"] == len(content)
    assert result["etag"] == "test-etag"


@pytest.mark.parametrize("name", ["S3_API_KEY", "CF_ACC_ID"])
def test_r2_requires_credentials(storage, monkeypatch, name):
    monkeypatch.delenv(name)
    with pytest.raises(ValueError, match="S3_API_KEY and CF_ACC_ID"):
        CloudflareR2()


@pytest.mark.parametrize("content", [b"", b"too large"])
def test_empty_and_oversized_files_never_reach_r2(storage, tmp_path, monkeypatch, content):
    monkeypatch.setattr(r2_storage, "MAX_DOCUMENT_BYTES", 3)
    path = tmp_path / "notes.txt"
    path.write_bytes(content)
    storage._client = SimpleNamespace(put_object=lambda **kwargs: pytest.fail("No request expected"))
    with pytest.raises(ValueError, match="Document size"):
        storage.upload_document(path, str(uuid4()))


@pytest.mark.parametrize("failure", [
    ClientError({"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}, "PutObject"),
    EndpointConnectionError(endpoint_url="https://test-account.r2.cloudflarestorage.com"),
])
def test_r2_request_failures_are_explicit(storage, tmp_path, monkeypatch, failure):
    path = tmp_path / "notes.txt"
    path.write_bytes(b"Evidence")

    def fail(*args, **kwargs):
        raise failure

    storage._client = SimpleNamespace(put_object=fail)
    with pytest.raises(StorageError) as caught:
        storage.upload_document(path, str(uuid4()))
    assert caught.value.__cause__ is failure
    assert "test-r2-token" not in str(caught.value)


def test_client_uses_configured_s3_endpoint_and_derived_credentials(storage, monkeypatch):
    def verify(request, timeout):
        assert request.full_url.endswith("/accounts/test-account/tokens/verify")
        assert request.get_header("Authorization") == "Bearer test-r2-token"
        return BytesIO(b'{"success":true,"result":{"id":"test-access-id","status":"active"}}')

    client = SimpleNamespace()

    def create(service, **kwargs):
        assert service == "s3"
        assert kwargs["endpoint_url"] == "https://test-account.r2.cloudflarestorage.com"
        assert kwargs["region_name"] == "auto"
        assert kwargs["aws_access_key_id"] == "test-access-id"
        assert kwargs["aws_secret_access_key"] == sha256(b"test-r2-token").hexdigest()
        assert kwargs["config"].signature_version == "s3v4"
        return client

    monkeypatch.setattr(r2_storage, "urlopen", verify)
    monkeypatch.setattr(r2_storage.boto3, "client", create)
    assert storage.client is client
    assert storage.client is client


def test_read_missing_object_returns_not_found(storage, monkeypatch):
    def missing(*args, **kwargs):
        raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

    storage._client = SimpleNamespace(get_object=missing)
    with pytest.raises(FileNotFoundError):
        storage.open_document("documents/missing.pdf")


def test_user_token_verification_falls_back_after_account_route_denial(storage, monkeypatch):
    calls = []

    def verify(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise HTTPError(request.full_url, 403, "Forbidden", {}, None)
        return BytesIO(b'{"success":true,"result":{"id":"user-access-id","status":"active"}}')

    monkeypatch.setattr(r2_storage, "urlopen", verify)
    access_id, secret = storage._s3_credentials()
    assert access_id == "user-access-id"
    assert calls[-1].endswith("/user/tokens/verify")
    assert secret == sha256(b"test-r2-token").hexdigest()


def test_token_verification_failure_stops_before_s3(storage, monkeypatch):
    monkeypatch.setattr(r2_storage, "urlopen", lambda *args, **kwargs: BytesIO(b'{"success":false}'))
    with pytest.raises(StorageError, match="verification failed"):
        storage._s3_credentials()


@pytest.mark.parametrize("error", [URLError("Connection failed"), TimeoutError("Timed out")])
def test_token_verification_network_failures_preserve_cause(storage, monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(r2_storage, "urlopen", fail)
    with pytest.raises(StorageError) as caught:
        storage._s3_credentials()
    assert caught.value.__cause__ is error


@pytest.mark.parametrize("endpoint", [
    "http://test-account.r2.cloudflarestorage.com",
    "https://other-account.r2.cloudflarestorage.com",
    "https://untrusted.example", "https://test-account.r2.cloudflarestorage.com/other-bucket",
])
def test_s3_endpoint_must_match_cloudflare_account(storage, monkeypatch, endpoint):
    monkeypatch.setenv("S3_API_URL", endpoint)
    with pytest.raises(ValueError, match="S3_API_URL"):
        CloudflareR2()


def test_dashboard_bucket_endpoint_does_not_duplicate_bucket_name(storage, monkeypatch):
    monkeypatch.setenv("S3_API_URL", "https://test-account.r2.cloudflarestorage.com/mynotebook")
    assert CloudflareR2()._endpoint == "https://test-account.r2.cloudflarestorage.com"


def test_stream_closes_provider_body_after_completion_and_interruption(monkeypatch):
    monkeypatch.setattr(r2_storage, "READ_SIZE", 2)
    body = BytesIO(b"abcdef")
    assert list(iter_document_bytes(body)) == [b"ab", b"cd", b"ef"]
    assert body.closed
    body = BytesIO(b"abcdef")
    stream = iter_document_bytes(body)
    assert next(stream) == b"ab"
    stream.close()
    assert body.closed


def test_ingestion_archives_before_indexing_and_keeps_metadata(monkeypatch, tmp_path):
    path = tmp_path / "notes.pdf"
    path.write_bytes(b"Original")
    calls = []
    monkeypatch.setattr(extractor.ExtractorFactory, "create", staticmethod(
        lambda _: SimpleNamespace(extract=lambda _: [{"page": 2, "texts": ["Evidence"]}]),
    ))
    sql = SimpleNamespace(
        select_chat_history=lambda **kwargs: {"summary": ""},
        validate_document_storage_schema=lambda: calls.append(("schema", None)),
        insert_document=lambda doc: calls.append(("sql", doc)),
        insert_chunks=lambda **kwargs: calls.append(("chunks", kwargs)),
    )

    def upload(upload_path, document_id):
        assert upload_path.read_bytes() == b"Original"
        calls.append(("r2", document_id))
        return {"storage_bucket": "mynotebook", "storage_key": f"documents/{document_id}.pdf", "file_size": 8}

    pipeline = Pipeline(
        sql=sql, storage=SimpleNamespace(upload_document=upload),
        qdrant=SimpleNamespace(add=lambda **kwargs: calls.append(("qdrant", kwargs))),
        embedding_model=SimpleNamespace(embed_passages=lambda texts: np.ones((len(texts), 1024), dtype=np.float32)),
    )
    doc = pipeline.insert_doc_pipeline(str(path), "user-1", "chat-1", "notes.pdf")
    assert [call[0] for call in calls] == ["schema", "r2", "sql", "chunks", "qdrant"]
    assert calls[2][1].storage_key == doc.storage_key
    assert calls[-1][1]["doc"].document_url == f"/documents/files/{doc.document_id}"


def test_failed_r2_upload_stops_sql_and_vector_insertion(monkeypatch, tmp_path):
    path = tmp_path / "notes.txt"
    path.write_bytes(b"Evidence")
    monkeypatch.setattr(extractor.ExtractorFactory, "create", staticmethod(lambda _: SimpleNamespace()))

    def fail(*args):
        raise StorageError("Upload failed")

    pipeline = Pipeline(
        sql=SimpleNamespace(
            select_chat_history=lambda **kwargs: {"summary": ""},
            validate_document_storage_schema=lambda: None,
            insert_document=lambda **kwargs: pytest.fail("SQL document insert must not happen"),
        ),
        qdrant=SimpleNamespace(), embedding_model=SimpleNamespace(),
        storage=SimpleNamespace(upload_document=fail),
    )
    with pytest.raises(StorageError):
        pipeline.insert_doc_pipeline(str(path), "user-1", "chat-1", "notes.txt")


def test_missing_storage_schema_stops_upload_before_r2(monkeypatch, tmp_path):
    path = tmp_path / "notes.txt"
    path.write_bytes(b"Evidence")
    monkeypatch.setattr(extractor.ExtractorFactory, "create", staticmethod(lambda _: SimpleNamespace()))

    def missing_schema():
        raise RuntimeError("Missing document storage columns")

    pipeline = Pipeline(
        sql=SimpleNamespace(select_chat_history=lambda **kwargs: {"summary": ""},
                            validate_document_storage_schema=missing_schema),
        qdrant=SimpleNamespace(), embedding_model=SimpleNamespace(),
        storage=SimpleNamespace(upload_document=lambda *args: pytest.fail("R2 must not be called")),
    )
    with pytest.raises(RuntimeError, match="storage columns"):
        pipeline.insert_doc_pipeline(str(path), "user-1", "chat-1", "notes.txt")


def test_citation_snapshots_include_stable_page_links_and_final_citations():
    registry = SourceRegistry()
    registry.register([RetrievalHit(
        document_id="doc-1", qdrant_point_id="point-1", content="Evidence",
        file_name="notes.pdf", page=2, score=0.5, retrieval_rank=1,
        document_url="/documents/files/doc-1",
    )])
    saved = []
    pipeline = Pipeline(
        sql=SimpleNamespace(update_chat_history=lambda **kwargs: saved.append(kwargs)),
        qdrant=SimpleNamespace(), embedding_model=SimpleNamespace(),
    )
    event = pipeline._finish_source_turn(
        "user-1", "chat-1", "question", "Answer [[source:1]] [[source:99]]", "", "turn-1",
        registry, SimpleNamespace(summarize_conversation=lambda **kwargs: "summary"),
    )
    assert event.payload["cited_source_ids"] == [1]
    assert event.payload["invalid_source_ids"] == [99]
    assert event.payload["citations"][0]["document_url"] == "/documents/files/doc-1#page=2"
    assert saved[0]["source_metadata"]["source_schema_version"] == 2
    assert saved[0]["source_metadata"]["sources"] == event.payload["citations"]


@pytest.fixture
def file_client(monkeypatch):
    monkeypatch.setenv("NOTEBOOK_SESSION_SECRET", "test-secret-with-at-least-32-characters")
    session_secret.cache_clear()
    bodies = []

    def select(document_id, user_id):
        if document_id == "doc-1" and user_id == "user-1":
            return {"document_id": "doc-1", "user_id": user_id, "type": ".pdf",
                    "file_name": "Ghi chú.pdf", "storage_bucket": "mynotebook", "storage_key": "documents/doc-1.pdf"}
        if document_id == "legacy":
            return {"document_id": "legacy", "user_id": user_id, "type": ".pdf"}
        return None

    def open_document(key):
        assert key == "documents/doc-1.pdf"
        body = BytesIO(b"%PDF-original")
        bodies.append(body)
        return body

    monkeypatch.setattr(document_api, "get_database", lambda: SimpleNamespace(select_document_for_user=select))
    monkeypatch.setattr(document_api, "get_storage", lambda: SimpleNamespace(bucket="mynotebook", open_document=open_document))
    app = FastAPI()
    app.include_router(document_api.router)
    with TestClient(app) as client:
        yield client, bodies
    session_secret.cache_clear()


def sign_in(client, user_id="user-1"):
    token = jwt.encode({"sub": user_id, "exp": 4102444800, "aud": "notebook", "iss": "notebook"},
                       session_secret(), algorithm="HS256")
    client.cookies.set(SESSION_COOKIE, token)


def test_original_file_requires_login_and_owner(file_client):
    client, bodies = file_client
    assert client.get("/documents/files/doc-1").status_code == 401
    sign_in(client, "user-2")
    assert client.get("/documents/files/doc-1").status_code == 404
    assert bodies == []


def test_original_file_streams_exact_bytes_without_exposing_credentials(file_client):
    client, bodies = file_client
    sign_in(client)
    response = client.get("/documents/files/doc-1")
    assert response.status_code == 200
    assert response.content == b"%PDF-original"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-disposition"].startswith("inline; filename*=UTF-8''Ghi%20")
    assert bodies[0].closed


def test_legacy_document_without_original_returns_404(file_client):
    client, bodies = file_client
    sign_in(client)
    assert client.get("/documents/files/legacy").status_code == 404
    assert bodies == []


def test_sql_persists_storage_metadata_and_filters_file_ownership():
    calls = []

    class SqlClient:
        def table(self, name):
            assert name == "document"
            return self

        def insert(self, row):
            calls.append(row)
            return self

        def select(self, fields):
            return self

        def eq(self, name, value):
            calls.append((name, value))
            return self

        def execute(self):
            return SimpleNamespace(data=[{"document_id": "doc-1"}])

    sql = Supabase_Manager.__new__(Supabase_Manager)
    sql.supabase = SqlClient()
    sql.insert_document(Document(
        document_id="doc-1", user_id="user-1", chat_id="chat-1", type=".pdf",
        storage_bucket="mynotebook", storage_key="documents/doc-1.pdf", file_size=10,
    ))
    assert calls[0]["storage_key"] == "documents/doc-1.pdf"
    assert "document_url" not in calls[0]
    assert sql.select_document_for_user("doc-1", "user-1") == {"document_id": "doc-1"}
    assert calls[1:] == [("document_id", "doc-1"), ("user_id", "user-1")]
