"""Cloudflare embedding contracts without external services."""

from io import BytesIO
import json
from urllib.error import HTTPError, URLError

import numpy as np
import pytest

from BackEnd.app.text_input import Embedding
from BackEnd.app.text_input.Embedding import EmbeddingModel


@pytest.fixture
def cloudflare(monkeypatch):
    monkeypatch.setenv("CF_API_KEY", "test-token")
    monkeypatch.delenv("CF_API_KEy", raising=False)
    monkeypatch.setenv("CF_ACC_ID", "test-account")
    calls = []

    def respond(request, timeout):
        texts = json.loads(request.data)["text"]
        calls.append(texts)
        assert request.full_url == (
            "https://api.cloudflare.com/client/v4/accounts/test-account"
            "/ai/run/@cf/baai/bge-m3"
        )
        assert request.get_header("Authorization") == "Bearer test-token"
        assert request.get_method() == "POST"
        assert timeout > 0
        vectors = np.zeros((len(texts), 1024), dtype=np.float32)
        for index, text in enumerate(texts):
            vectors[index, int(text.split()[-1])] = 2.0
        return BytesIO(json.dumps({
            "success": True, "result": {"data": vectors.tolist()},
        }).encode())

    monkeypatch.setattr(Embedding, "urlopen", respond)
    return calls


def test_passages_are_batched_in_order_and_normalized(cloudflare):
    texts = [f"Vietnamese document {index}" for index in range(35)]
    vectors = EmbeddingModel().embed_passages(texts)

    assert cloudflare == [texts[:32], texts[32:]]
    assert vectors.shape == (35, 1024)
    assert vectors.dtype == np.float32
    assert vectors.flags.c_contiguous
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1.0)
    np.testing.assert_array_equal(np.argmax(vectors, axis=1), np.arange(35))


def test_query_has_no_e5_prefix_and_returns_one_vector(cloudflare):
    vector = EmbeddingModel().embed_query("Vietnamese query 7")

    assert cloudflare == [["Vietnamese query 7"]]
    assert vector.shape == (1024,)
    assert vector.dtype == np.float32
    assert vector[7] == 1.0


def test_empty_passages_and_dimension_need_no_api_call(monkeypatch):
    monkeypatch.delenv("CF_API_KEY", raising=False)
    monkeypatch.delenv("CF_API_KEy", raising=False)
    monkeypatch.delenv("CF_ACC_ID", raising=False)
    model = EmbeddingModel()

    assert model.dimension == 1024
    assert model.embed_passages([]).shape == (0, 1024)


@pytest.mark.parametrize("name", ["CF_API_KEY", "CF_ACC_ID"])
def test_missing_credentials_fail_clearly(cloudflare, monkeypatch, name):
    monkeypatch.delenv(name)

    with pytest.raises(ValueError, match="CF_API_KEY and CF_ACC_ID"):
        EmbeddingModel().embed_query("query")
    assert cloudflare == []


def test_existing_api_key_casing_is_supported(cloudflare, monkeypatch):
    monkeypatch.delenv("CF_API_KEY")
    monkeypatch.setenv("CF_API_KEy", "test-token")

    assert EmbeddingModel().embed_query("query 1").shape == (1024,)


def test_standard_api_key_takes_precedence(cloudflare, monkeypatch):
    monkeypatch.setenv("CF_API_KEy", "unused-token")

    assert EmbeddingModel().embed_query("query 1").shape == (1024,)


@pytest.mark.parametrize("payload,error", [
    ({"success": False}, RuntimeError),
    ({"success": True, "result": {}}, ValueError),
    ({"success": True, "result": {"data": [[1.0] * 768]}}, ValueError),
    ({"success": True, "result": {"data": [[0.0] * 1024]}}, ValueError),
    ({"success": True, "result": {"data": [[float("nan")] * 1024]}}, ValueError),
])
def test_invalid_api_vectors_are_rejected(cloudflare, monkeypatch, payload, error):
    monkeypatch.setattr(
        Embedding, "urlopen",
        lambda *args, **kwargs: BytesIO(json.dumps(payload).encode()),
    )
    with pytest.raises(error):
        EmbeddingModel().embed_query("query")


@pytest.mark.parametrize("error", [
    HTTPError("https://api.cloudflare.com", 401, "Unauthorized", {}, None),
    URLError("Connection failed"),
    TimeoutError("Request timed out"),
])
def test_request_errors_preserve_the_cause(cloudflare, monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(Embedding, "urlopen", fail)
    with pytest.raises(RuntimeError, match="Cloudflare") as caught:
        EmbeddingModel().embed_query("query")
    assert caught.value.__cause__ is error
