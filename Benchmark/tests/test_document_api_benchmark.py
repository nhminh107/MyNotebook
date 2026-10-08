import importlib.util
import io
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "document_api_benchmark", Path(__file__).resolve().parents[1] / "run_document_api.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_sse_preserves_native_sources_and_invalid_markers() -> None:
    stream = io.BytesIO(
        b'event: sources\ndata: {"sources": [{"citation_id": 1, "page": 3}]}\n\n'
        b'event: token\ndata: {"content": "alpha [[source:9]]"}\n\n'
        b'event: citations\ndata: {"cited_source_ids": []}\n\n'
        b'event: done\ndata: {}\n\n'
    )
    result = module.parse_stream(stream)
    assert result["done"]
    assert result["sources"][0]["page"] == 3
    assert result["cited_ids"] == [9]
    assert result["stream_ttft_ms"] is not None


def test_sse_errors_and_empty_tokens_cannot_look_successful() -> None:
    result = module.parse_stream(io.BytesIO(
        b'event: token\ndata: {"content": ""}\n\n'
        b'event: error\ndata: {"message": "failure"}\n\n'
    ))
    assert result["errors"]
    assert not result["done"]
    assert result["stream_ttft_ms"] is None


def test_native_unknown_filename_cannot_match_gold_document() -> None:
    hits = module.native_hits(
        [{"file_name": "unknown.pdf", "page": 1, "content": "alpha", "citation_id": 1}],
        {"documents": [{"id": "doc", "path": "known.pdf"}]},
    )
    assert hits[0]["page_id"] == "unknown"


def test_citation_examples_in_code_are_not_scored_as_claims() -> None:
    result = module.parse_stream(io.BytesIO(
        b'event: token\ndata: {"content": "`[[source:1]]` alpha [[source:2]]"}\n\n'
        b'event: done\ndata: {}\n\n'
    ))
    assert result["cited_ids"] == [2]
