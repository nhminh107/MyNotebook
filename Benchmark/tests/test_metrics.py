from rag_benchmark.metrics import evaluate_answer, evaluate_retrieval, normalize_text, token_f1


def test_normalize_text_is_case_and_punctuation_insensitive() -> None:
    assert normalize_text("  Việt-RAG! ") == "việt rag"


def test_token_f1_is_one_for_equivalent_text() -> None:
    assert token_f1("Qdrant dùng RRF.", "qdrant dùng rrf") == 1.0


def test_retrieval_metrics_known_ranking() -> None:
    result = evaluate_retrieval(["a", "b", "c"], ["b", "c"], 3)
    assert result["hit_rate@3"] == 1.0
    assert result["recall@3"] == 1.0
    assert result["precision@3"] == 2 / 3
    assert result["mrr"] == 0.5
    assert 0.0 < result["ndcg@3"] < 1.0


def test_answer_metrics_detect_facts_and_abstention() -> None:
    result = evaluate_answer(
        "Tài liệu không cung cấp thông tin về Sao Hỏa.",
        "Không có thông tin.",
        ["Sao Hỏa"],
        ["Tài liệu mô tả Sao Hỏa."],
        expected_abstain=True,
    )
    assert result["fact_coverage"] == 1.0
    assert result["abstention_accuracy"] == 1.0
    assert result["faithfulness"] > 0.0

