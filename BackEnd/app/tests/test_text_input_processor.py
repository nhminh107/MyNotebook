import json

import faiss
import numpy as np

from BackEnd.app.database.faiss_manager import Faiss
from BackEnd.app.text_input import text_input_processor
from BackEnd.app.text_input.text_input_processor import TextInputProcessor


class FakeEmbeddingModel:
    """Fixed vectors: avoids downloading VietRAG-Embed in a unit test."""

    dimension = 3

    def embed_passages(self, texts):
        return np.array(
            [[1.0, 0.0, 0.0] if "FAISS" in text else [0.0, 1.0, 0.0] for text in texts],
            dtype=np.float32,
        )

    def embed_query(self, text):
        return np.array([1.0, 0.0, 0.0], dtype=np.float32)


class FakeDatabase:
    def __init__(self):
        self.documents = []
        self.chunks = []

    def insert_document(self, document):
        self.documents.append(document)

    def insert_chunks(self, chunk):
        self.chunks.append(chunk)


def make_temp_faiss_store(tmp_path):
    """Use the real Faiss methods but direct all generated files to pytest's temp folder."""
    store = object.__new__(Faiss)
    store.dimension = 3
    store.index_path = tmp_path / "vietrag.index"
    store.records_path = tmp_path / "vietrag.records.json"
    store.index = faiss.IndexIDMap2(faiss.IndexFlatIP(3))
    store.records = {}
    return store


def test_process_creates_faiss_records_and_calls_sql_inserts(tmp_path, monkeypatch):
    monkeypatch.setattr(
        text_input_processor,
        "_chunk_text",
        lambda _: ["FAISS lưu vector để tìm kiếm.", "VietRAG-Embed hỗ trợ tiếng Việt."],
    )
    database = FakeDatabase()
    store = make_temp_faiss_store(tmp_path)
    processor = TextInputProcessor(
        database=database,
        embedder=FakeEmbeddingModel(),
        faiss_store=store,
    )

    result = processor.process(user_id="user-001", text="Đoạn văn bất kỳ")

    assert result["chunk_count"] == 2
    assert len(result["faiss_ids"]) == 2
    assert len(database.documents) == 1
    assert len(database.chunks) == 2
    assert store.index.ntotal == 2
    assert store.index_path.exists()
    assert store.records_path.exists()

    records = json.loads(store.records_path.read_text(encoding="utf-8"))
    assert set(records) == {str(faiss_id) for faiss_id in result["faiss_ids"]}

    matches = processor.search("FAISS dùng để làm gì?", limit=1)
    assert matches[0]["content"] == "FAISS lưu vector để tìm kiếm."
