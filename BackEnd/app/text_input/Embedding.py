from __future__ import annotations

from abc import ABC, abstractmethod
import os
from dotenv import load_dotenv
import numpy as np
from huggingface_hub import InferenceClient

load_dotenv()
class BaseEmbeddingModel(ABC):
    @abstractmethod
    def embed_passages(self, texts: list[str]) -> np.ndarray:
        pass

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray:
        pass


class EmbeddingModel(BaseEmbeddingModel):

    model_name = "intfloat/multilingual-e5-base"
    # Dùng URL trực tiếp tới pipeline feature-extraction để bỏ qua bước check
    # pipeline_tag phía client (model này được gắn tag 'sentence-similarity').
    api_url = (
        f"https://router.huggingface.co/hf-inference/models/{model_name}"
        "/pipeline/feature-extraction"
    )

    def __init__(self) -> None:
        self._model = None
        self._dimension: int | None = None

    @property
    def model(self) -> InferenceClient:
        if self._model is None:
            self._model = InferenceClient(
                provider="hf-inference",
                api_key=os.environ["HF_TOKEN"],
                model=self.api_url,
            )
        return self._model

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._dimension = int(self._embed(["dimension probe"]).shape[1])
        return self._dimension

    def _embed(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            vec = np.asarray(self.model.feature_extraction(text), dtype=np.float32)
            # Nếu API trả về token-level (tokens, dim) hoặc (1, dim) -> mean pooling
            while vec.ndim > 1:
                vec = vec.mean(axis=0)
            rows.append(vec)
        vectors = np.stack(rows)
        # Tự normalize (thay cho normalize_embeddings=True)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / np.clip(norms, 1e-12, None)
        return np.ascontiguousarray(vectors, dtype=np.float32)

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._embed([f"passage: {text}" for text in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([f"query: {text}"])[0]