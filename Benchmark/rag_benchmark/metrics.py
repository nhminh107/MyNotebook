from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Iterable, Sequence


TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
ABSTENTION_MARKERS = (
    "không có thông tin",
    "không cung cấp",
    "không đủ thông tin",
    "không tìm thấy",
    "cannot find",
    "not enough information",
    "does not provide",
)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(TOKEN_PATTERN.findall(value))


def token_f1(prediction: str, reference: str) -> float:
    predicted = normalize_text(prediction).split()
    expected = normalize_text(reference).split()
    if not predicted or not expected:
        return float(predicted == expected)
    common = sum((Counter(predicted) & Counter(expected)).values())
    if common == 0:
        return 0.0
    precision = common / len(predicted)
    recall = common / len(expected)
    return 2 * precision * recall / (precision + recall)


def fact_coverage(answer: str, required_facts: Sequence[str]) -> float:
    if not required_facts:
        return 1.0
    normalized = normalize_text(answer)
    return sum(normalize_text(fact) in normalized for fact in required_facts) / len(required_facts)


def lexical_faithfulness(answer: str, contexts: Sequence[str]) -> float:
    """Fraction of answer content tokens supported by retrieved contexts.

    This is a deterministic proxy, not an LLM judge. Use it for regressions and
    pair it with human/LLM-judge review for release evaluation.
    """
    answer_tokens = set(normalize_text(answer).split())
    context_tokens = set(normalize_text(" ".join(contexts)).split())
    if not answer_tokens:
        return 0.0
    return len(answer_tokens & context_tokens) / len(answer_tokens)


def evaluate_answer(
    answer: str,
    reference: str,
    required_facts: Sequence[str] = (),
    contexts: Sequence[str] = (),
    expected_abstain: bool = False,
) -> dict[str, float]:
    abstained = any(marker in normalize_text(answer) for marker in ABSTENTION_MARKERS)
    return {
        "exact_match": float(normalize_text(answer) == normalize_text(reference)),
        "token_f1": token_f1(answer, reference),
        "fact_coverage": fact_coverage(answer, required_facts),
        "faithfulness": lexical_faithfulness(answer, contexts) if contexts else 0.0,
        "answer_relevancy": token_f1(answer, reference),
        "abstention_accuracy": float(abstained == expected_abstain),
    }


def evaluate_retrieval(
    retrieved_ids: Sequence[str],
    relevant_ids: Iterable[str],
    k: int,
) -> dict[str, float]:
    relevant = set(relevant_ids)
    top_k = list(retrieved_ids[:k])
    hits = [item for item in top_k if item in relevant]
    first_rank = next((rank for rank, item in enumerate(top_k, 1) if item in relevant), None)
    dcg = sum((1.0 / math.log2(rank + 1)) for rank, item in enumerate(top_k, 1) if item in relevant)
    ideal_count = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return {
        f"hit_rate@{k}": float(bool(hits)),
        f"recall@{k}": len(set(hits)) / len(relevant) if relevant else 1.0,
        f"precision@{k}": len(hits) / k if k else 0.0,
        "mrr": 1.0 / first_rank if first_rank else 0.0,
        f"ndcg@{k}": dcg / idcg if idcg else 1.0,
    }

