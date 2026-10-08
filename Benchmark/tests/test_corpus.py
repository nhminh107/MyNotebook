"""Quality checks that guard gold evidence, rankings and exported answers."""

import pytest

from rag_benchmark.corpus import (
    BM25Index, evaluate_predictions, score_retrieval, validate_dataset,
)


def make_case(abstain: bool = False) -> dict:
    return {"id": "q1", "question": "What is the value?", "split": "test",
            "category": "factual", "reference_answer": "alpha",
            "required_facts": ["alpha"], "expected_abstain": abstain,
            "evidence": [] if abstain else [{"document_id": "doc", "page": 1, "quote": "alpha"}]}


def make_chunk(index: int, page: int, text: str) -> dict:
    return {"id": f"doc:p{page}:c{index}", "document_id": "doc", "page": page,
            "page_id": f"doc:p{page}", "content": text}


def test_gold_quote_must_be_on_its_declared_page() -> None:
    with pytest.raises(ValueError, match="Unverified gold quote"):
        validate_dataset({"cases": [make_case()]}, {"doc:p1": "beta"})


def test_duplicate_questions_cannot_enter_other_split() -> None:
    case = make_case()
    with pytest.raises(ValueError, match="Duplicate"):
        validate_dataset({"cases": [case, {**case, "id": "q2", "split": "dev"}]}, {"doc:p1": "alpha"})


def test_negative_case_cannot_have_positive_evidence() -> None:
    case = {**make_case(), "expected_abstain": True}
    with pytest.raises(ValueError, match="Evidence/abstention"):
        validate_dataset({"cases": [case]}, {"doc:p1": "alpha"})


def test_bm25_does_not_return_zero_score_matches() -> None:
    index = BM25Index([make_chunk(0, 1, "alpha alpha"), make_chunk(1, 2, "beta")])
    assert index.search("alpha", 3)[0]["page"] == 1
    assert index.search("unmatched", 3) == []


def test_duplicate_page_chunks_do_not_inflate_precision_or_ndcg() -> None:
    chunks = [make_chunk(0, 1, "alpha"), make_chunk(1, 1, "alpha")]
    scores = score_retrieval(make_case(), chunks, 2)
    assert scores["precision@2"] == 0.5
    assert scores["ndcg@2"] == 1.0
    assert scores["evidence_coverage"] == 1.0


def test_page_hit_does_not_imply_quote_coverage() -> None:
    scores = score_retrieval(make_case(), [make_chunk(0, 1, "beta")], 1)
    assert scores["recall@1"] == 1.0
    assert scores["evidence_coverage"] == 0.0


def test_prediction_run_must_cover_the_entire_split() -> None:
    with pytest.raises(ValueError, match="match the selected split"):
        evaluate_predictions([make_case()], [], [])


def test_prediction_rejects_unknown_context_ids() -> None:
    prediction = {"id": "q1", "answer": "alpha", "retrieved_ids": ["missing"], "cited_ids": []}
    with pytest.raises(ValueError, match="Unknown prediction"):
        evaluate_predictions([make_case()], [prediction], [])


def test_citing_gold_page_outside_retrieved_context_gets_no_credit() -> None:
    chunks = [make_chunk(0, 1, "alpha"), make_chunk(0, 2, "beta")]
    prediction = {"id": "q1", "answer": "alpha", "retrieved_ids": [chunks[1]["id"]], "cited_ids": [chunks[0]["id"]]}
    metrics, _ = evaluate_predictions([make_case()], [prediction], chunks)
    assert metrics["answer_citation_page_precision"] == 0.0
    assert metrics["answer_lexical_faithfulness_proxy"] == 0.0


def test_citation_markers_are_excluded_from_answer_metrics() -> None:
    chunk = make_chunk(0, 1, "alpha")
    prediction = {"id": "q1", "answer": "alpha [[source:1]]", "retrieved_ids": [chunk["id"]], "cited_ids": [chunk["id"]]}
    metrics, _ = evaluate_predictions([make_case()], [prediction], [chunk])
    assert metrics["answer_exact_match"] == 1.0
    assert metrics["answer_citation_page_recall"] == 1.0


def test_negatives_are_not_averaged_into_positive_answer_quality() -> None:
    case = make_case(True)
    prediction = {"id": "q1", "answer": "Tài liệu không cung cấp thông tin này.", "retrieved_ids": [], "cited_ids": []}
    metrics, _ = evaluate_predictions([case], [prediction], [])
    assert metrics["negative_abstention_accuracy"] == 1.0
    assert "answer_fact_coverage" not in metrics


def test_short_option_fact_requires_a_whole_token() -> None:
    case = {**make_case(), "required_facts": ["B"]}
    chunk = make_chunk(0, 1, "about alpha")
    prediction = {"id": "q1", "answer": "about alpha", "retrieved_ids": [chunk["id"]], "cited_ids": []}
    metrics, _ = evaluate_predictions([case], [prediction], [chunk])
    assert metrics["answer_fact_coverage"] == 0.0
