from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class BaseEmbeddingModel(ABC):
    @abstractmethod
    def embed_passages(self, texts: list[str]) -> np.ndarray:
        pass

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray:
        pass


class EmbeddingModel(BaseEmbeddingModel):

    model_name = "nhminh107/VietRAG-Embed"

    def __init__(self) -> None:
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dimension(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())

    def _embed(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )
        return np.ascontiguousarray(vectors, dtype=np.float32)

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._embed([f"passage: {text}" for text in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([f"query: {text}"])[0]