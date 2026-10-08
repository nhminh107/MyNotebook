from __future__ import annotations

from abc import ABC, abstractmethod
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
import numpy as np

from BackEnd.app.CONFIG import EMBEDDING_SIZE

load_dotenv()


class BaseEmbeddingModel(ABC):
    @abstractmethod
    def embed_passages(self, texts: list[str]) -> np.ndarray:
        pass

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray:
        pass


class EmbeddingModel(BaseEmbeddingModel):
    """Normalized dense embeddings from Cloudflare Workers AI BGE-M3."""

    model_name = "@cf/baai/bge-m3"
    BATCH_SIZE = 32
    TIMEOUT_SECONDS = 60

    @property
    def dimension(self) -> int:
        return EMBEDDING_SIZE

    def _embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        # Support the existing variable's casing without editing credentials.
        api_key = os.getenv("CF_API_KEY")
        account_id = os.getenv("CF_ACC_ID")
        if not api_key or not account_id:
            raise ValueError("CF_API_KEY and CF_ACC_ID are required for embeddings.")

        api_url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
            f"/ai/run/{self.model_name}"
        )
        rows = []
        for start in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[start:start + self.BATCH_SIZE]
            request = Request(
                api_url,
                data=json.dumps({"text": batch}).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=self.TIMEOUT_SECONDS) as response:
                    payload = json.load(response)
            except HTTPError as exc:
                raise RuntimeError(
                    f"Cloudflare embedding request failed (HTTP {exc.code})."
                ) from exc
            except (URLError, TimeoutError) as exc:
                raise RuntimeError("Cloudflare embedding request failed.") from exc

            if not payload.get("success"):
                raise RuntimeError("Cloudflare reported an embedding failure.")
            result = payload.get("result") or {}
            vectors = np.asarray(result.get("data"), dtype=np.float32)
            if vectors.shape != (len(batch), self.dimension):
                raise ValueError(
                    f"Expected Cloudflare embeddings of shape "
                    f"{(len(batch), self.dimension)}, received {vectors.shape}."
                )
            if not np.isfinite(vectors).all() or np.any(
                np.linalg.norm(vectors, axis=1) == 0
            ):
                raise ValueError("Cloudflare returned invalid embedding vectors.")
            rows.append(vectors)

        vectors = np.concatenate(rows, axis=0)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / np.clip(norms, 1e-12, None)
        return np.ascontiguousarray(vectors, dtype=np.float32)

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([text])[0]
