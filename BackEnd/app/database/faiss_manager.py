from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import faiss
import numpy as np


class Faiss:

    def __init__(self, dimension: int) -> None:
        data_dir = Path(__file__).resolve().parents[2] / "data"
        self.index_path = data_dir / "vietrag.index"
        self.records_path = data_dir / "vietrag.records.json"
        self.dimension = dimension
        self.index = self._load_index()
        self.records = self._load_records()

    def _load_index(self) -> faiss.Index:
        if not self.index_path.exists():
            return faiss.IndexIDMap2(faiss.IndexFlatIP(self.dimension))
        index = faiss.read_index(str(self.index_path))
        if index.d != self.dimension:
            raise ValueError("The existing FAISS index uses another embedding dimension.")
        return index

    def _load_records(self) -> dict[str, dict]:
        if not self.records_path.exists():
            return {}
        return json.loads(self.records_path.read_text(encoding="utf-8"))

    def add(self, vectors: np.ndarray, records: list[dict]) -> list[int]:
        if len(vectors) != len(records):
            raise ValueError("Every FAISS vector must have one record.")
        faiss_ids = [uuid4().int >> 65 for _ in records]
        self.index.add_with_ids(
            np.ascontiguousarray(vectors, dtype=np.float32),
            np.asarray(faiss_ids, dtype=np.int64),
        )
        self.records.update(
            {str(faiss_id): record for faiss_id, record in zip(faiss_ids, records)}
        )
        self._save()
        return faiss_ids

    def rollback(self, faiss_ids: list[int]) -> None:
        self.index.remove_ids(np.asarray(faiss_ids, dtype=np.int64))
        for faiss_id in faiss_ids:
            self.records.pop(str(faiss_id), None)
        self._save()

    def search(self, query_vector: np.ndarray, limit: int = 5) -> list[dict]:
        scores, ids = self.index.search(
            np.ascontiguousarray(query_vector, dtype=np.float32).reshape(1, -1), limit
        )
        return [
            {"faiss_id": int(faiss_id), "score": float(score), **self.records[str(faiss_id)]}
            for faiss_id, score in zip(ids[0], scores[0])
            if faiss_id != -1 and str(faiss_id) in self.records
        ]

    def _save(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_index()
        self._atomic_write_records()

    def _atomic_write_index(self) -> None:
        file_handle, temporary_name = tempfile.mkstemp(suffix=".index", dir=self.index_path.parent)
        os.close(file_handle)
        temporary_path = Path(temporary_name)
        try:
            faiss.write_index(self.index, str(temporary_path))
            os.replace(temporary_path, self.index_path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _atomic_write_records(self) -> None:
        file_handle, temporary_name = tempfile.mkstemp(suffix=".json", dir=self.records_path.parent)
        os.close(file_handle)
        temporary_path = Path(temporary_name)
        try:
            temporary_path.write_text(json.dumps(self.records, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary_path, self.records_path)
        finally:
            temporary_path.unlink(missing_ok=True)