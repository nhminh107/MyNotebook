"""Regressions for uploads against old SQL schemas and long source text."""

from copy import deepcopy
from types import SimpleNamespace

import numpy as np
from postgrest import APIError
import pytest

from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.database.sql_models import Chunk
from BackEnd.app.doc_extractor import extractor, texts_chunking
from BackEnd.app.pipeline import Pipeline

BASE_COLUMNS = {"chunk_id", "document_id", "content"}
METADATA_COLUMNS = {"page", "chunk_index", "ocr_used"}


class SchemaClient:
    """Reject unknown columns before inserting, as PostgREST does."""

    def __init__(self, columns: set[str]) -> None:
        self.columns = columns
        self.calls: list[list[dict]] = []
        self.rows: list[dict] = []
        self.error: APIError | None = None

    def table(self, name: str):
        assert name == "chunks"
        return self

    def insert(self, data: list[dict]):
        self.pending = deepcopy(data)
        self.calls.append(self.pending)
        return self

    def execute(self):
        if self.error is not None:
            raise self.error
        unknown = set(self.pending[0]) - self.columns
        if unknown:
            column = sorted(unknown)[0]
            raise APIError({
                "message": f"Could not find the '{column}' column of 'chunks' in the schema cache",
                "code": "PGRST204", "hint": None, "details": None,
            })
        self.rows.extend(deepcopy(self.pending))
        return SimpleNamespace(data=self.pending)


def manager(columns: set[str]) -> Supabase_Manager:
    instance = Supabase_Manager.__new__(Supabase_Manager)
    instance.supabase = SchemaClient(columns)
    return instance


def chunk(chunk_id: str = "chunk-1") -> Chunk:
    return Chunk(
        chunk_id=chunk_id, document_id="doc-1", content="Evidence\x00",
        page=3, chunk_index=7, ocr_used=True,
    )


def test_old_schema_upload_falls_back_without_duplicate_rows(caplog) -> None:
    sql = manager(BASE_COLUMNS)
    result = sql.insert_chunks([chunk()])
    assert result == [{"chunk_id": "chunk-1", "document_id": "doc-1", "content": "Evidence"}]
    assert len(sql.supabase.rows) == 1
    assert len(sql.supabase.calls) == 4
    assert sql._missing_chunk_metadata == METADATA_COLUMNS
    assert "Qdrant and citation snapshots retain source metadata" in caplog.text
    sql.insert_chunks([chunk("chunk-2")])
    assert len(sql.supabase.calls) == 5
    assert len(sql.supabase.rows) == 2


def test_partially_migrated_schema_preserves_available_metadata() -> None:
    sql = manager(BASE_COLUMNS | {"page"})
    result = sql.insert_chunks([chunk()])
    assert result[0]["page"] == 3
    assert "chunk_index" not in result[0]
    assert "ocr_used" not in result[0]
    assert chunk().chunk_index == 7


def test_migrated_schema_stores_all_metadata_without_retry() -> None:
    sql = manager(BASE_COLUMNS | METADATA_COLUMNS)
    result = sql.insert_chunks([chunk()])
    assert result[0]["page"] == 3
    assert result[0]["chunk_index"] == 7
    assert result[0]["ocr_used"] is True
    assert len(sql.supabase.calls) == 1


@pytest.mark.parametrize("code,message", [
    ("PGRST204", "Could not find the 'document_id' column of 'chunks' in the schema cache"),
    ("PGRST204", "Could not find the 'page' column of 'document' in the schema cache"),
    ("23505", "duplicate key value violates unique constraint"),
    ("42501", "permission denied for table chunks"),
])
def test_unrelated_sql_errors_are_never_retried_or_hidden(code, message) -> None:
    sql = manager(BASE_COLUMNS)
    sql.supabase.error = APIError({"code": code, "message": message, "hint": None, "details": None})
    with pytest.raises(APIError) as caught:
        sql.insert_chunks([chunk()])
    assert caught.value is sql.supabase.error
    assert len(sql.supabase.calls) == 1
    assert sql.supabase.rows == []


def test_pipeline_retains_qdrant_metadata_after_sql_fallback(monkeypatch) -> None:
    sql = manager(BASE_COLUMNS)
    sql.select_chat_history = lambda **kwargs: {"conversation": []}
    sql.insert_document = lambda **kwargs: None
    monkeypatch.setattr(extractor.ExtractorFactory, "create", staticmethod(
        lambda _: SimpleNamespace(extract=lambda _: [{"page": 3, "texts": ["Evidence"], "ocr_used": True}])
    ))
    calls = []
    pipeline = Pipeline(
        sql=sql, qdrant=SimpleNamespace(add=lambda **kwargs: calls.append(kwargs)),
        embedding_model=SimpleNamespace(embed_passages=lambda texts: np.ones((len(texts), 2), dtype=np.float32)),
    )
    pipeline.insert_doc_pipeline("notes.pdf", "user-1", "chat-1", "notes.pdf")
    stored_chunk = calls[0]["chunks"][0]
    assert stored_chunk.page == 3
    assert stored_chunk.chunk_index == 0
    assert stored_chunk.ocr_used is True
    assert sql.supabase.rows[0]["chunk_id"] == stored_chunk.chunk_id


def test_counting_long_text_is_untruncated_and_final_chunks_are_bounded(caplog, monkeypatch) -> None:
    monkeypatch.setattr(texts_chunking.tokenizer, "deprecation_warnings", {})
    text = "document evidence " * 700
    total = texts_chunking.token_length(text)
    assert total > texts_chunking.tokenizer.model_max_length
    chunks = texts_chunking.chunking(text)
    assert len(chunks) > 1
    assert all(texts_chunking.token_length(part) <= texts_chunking.CHUNKING_SIZE for part in chunks)
    assert all(
        len(texts_chunking.tokenizer.encode(f"passage: {part}", verbose=False)) <= 512
        for part in chunks
    )
    assert not any("sequence length" in record.message for record in caplog.records)
    # Repeated evidence after the first 512 tokens must still reach later chunks.
    assert sum(texts_chunking.token_length(part) for part in chunks) >= total
