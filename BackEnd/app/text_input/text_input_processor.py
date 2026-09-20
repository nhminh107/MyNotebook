from __future__ import annotations

from uuid import uuid4
from abc import ABC, abstractmethod
from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.database.sql_models import Chunk, Document
from BackEnd.app.text_input.Embedding import (EmbeddingModel,)
from BackEnd.app.database.faiss_manager import (Faiss,)


def _chunk_text(text: str) -> list[str]:
    """Import lazily so unit tests do not download the tokenizer."""
    from BackEnd.app.doc_extractor.texts_chunking import chunking

    return chunking(text)


class BaseInputProcessor(ABC):
    @abstractmethod
    def process(self, user_id: str, text: str) -> dict:
        pass


class TextInputProcessor(BaseInputProcessor):

    def __init__(
        self,
        database: Supabase_Manager | None = None,
        embedder: EmbeddingModel | None = None,
        faiss_store: Faiss | None = None,
    ) -> None:
        self.database = database or Supabase_Manager()
        self.embedder = embedder or EmbeddingModel()
        self.faiss_store = faiss_store or Faiss(self.embedder.dimension)

    def process(self, user_id: str, text: str) -> dict:
        texts = _chunk_text(text)
        if not texts:
            raise ValueError("Input text is empty.")

        document_id = str(uuid4())
        chunks = [Chunk(chunk_id=str(uuid4()), document_id=document_id, content=content) for content in texts]
        vectors = self.embedder.embed_passages(texts)

        faiss_ids = self.faiss_store.add(
            vectors,
            [
                {"chunk_id": chunk.chunk_id, "document_id": document_id, "content": chunk.content, "chunk_index": index}
                for index, chunk in enumerate(chunks)
            ],
        )

        try:
            self.database.insert_document(Document(document_id=document_id, user_id=user_id, type="text"))
            for chunk in chunks:
                self.database.insert_chunks(chunk)
        except Exception:
            self.faiss_store.rollback(faiss_ids)
            raise

        return {"document_id": document_id, "chunk_count": len(chunks), "faiss_ids": faiss_ids}

    def search(self, query: str, limit: int = 5) -> list[dict]:
        return self.faiss_store.search(self.embedder.embed_query(query), limit)
