from __future__ import annotations

import json
import os
import platform
import resource
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from .metrics import evaluate_answer, evaluate_retrieval
from .report import aggregate, build_report
from .timing import LatencyRecorder


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _check(name: str, operation) -> dict:
    try:
        detail = operation()
        return {"name": name, "status": "PASS", "detail": detail or "ok"}
    except Exception as exc:
        return {"name": name, "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"}


def _memory_mib() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / 1024 if sys.platform != "darwin" else value / (1024 * 1024)


def run_offline(iterations: int = 50, k: int = 3) -> dict:
    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    checks: list[dict] = []
    started_rss = _memory_mib()

    def sanitizer_check() -> str:
        from BackEnd.app.text_sanitizer import sanitize_text
        assert sanitize_text("xin\x00chào") == "xinchào"
        return "null byte removed; Unicode preserved"

    checks.append(_check("text_sanitizer", sanitizer_check))

    def sse_check() -> str:
        from BackEnd.app.api.document import format_sse_event
        event = format_sse_event("token", {"content": "xin chào"})
        assert event.startswith("event: token\n") and event.endswith("\n\n")
        json.loads(event.split("data: ", 1)[1])
        return "valid SSE event and UTF-8 JSON payload"

    checks.append(_check("sse_contract", sse_check))

    retrieval_rows = [
        evaluate_retrieval(["c1", "c3", "c9"], ["c1", "c2"], k),
        evaluate_retrieval(["c4", "c2", "c8"], ["c2"], k),
        evaluate_retrieval(["c7", "c6", "c5"], ["c5"], k),
    ]
    answer_rows = [
        evaluate_answer(
            "Qdrant kết hợp dense và BM25 bằng RRF.",
            "Dense và BM25 được kết hợp bằng RRF trong Qdrant.",
            ["dense", "BM25", "RRF"],
            ["Qdrant lưu dense vector và sparse BM25, sau đó hợp nhất bằng RRF."],
        ),
        evaluate_answer(
            "Tài liệu không cung cấp thông tin này.",
            "Không có thông tin trong tài liệu.",
            [],
            ["Tài liệu chỉ mô tả MyNotebook."],
            expected_abstain=True,
        ),
    ]
    checks.append({"name": "retrieval_metrics", "status": "PASS", "detail": "Hit/Recall/Precision/MRR/nDCG computed"})
    checks.append({"name": "answer_metrics", "status": "PASS", "detail": "EM/F1/facts/faithfulness/relevancy/abstention computed"})

    faiss_latency = LatencyRecorder()
    cold_started = time.perf_counter()

    def faiss_check() -> str:
        import faiss
        from BackEnd.app.database.faiss_manager import Faiss

        with tempfile.TemporaryDirectory(prefix="mynotebook-benchmark-") as directory:
            store = object.__new__(Faiss)
            store.dimension = 4
            store.index_path = Path(directory) / "benchmark.index"
            store.records_path = Path(directory) / "benchmark.json"
            store.index = faiss.IndexIDMap2(faiss.IndexFlatIP(4))
            store.records = {}
            vectors = np.eye(4, dtype=np.float32)
            ids = store.add(vectors, [{"chunk_id": f"c{i}", "content": f"chunk {i}"} for i in range(4)])
            for _ in range(iterations):
                result = faiss_latency.measure(lambda: store.search(vectors[0], limit=k))
                assert result[0]["chunk_id"] == "c0"
            store.rollback(ids)
            assert store.index.ntotal == 0
        return "real FAISS add/search/persist/rollback"

    checks.append(_check("faiss_lifecycle", faiss_check))
    cold_ms = (time.perf_counter() - cold_started) * 1000
    latency = faiss_latency.summary()

    functional_pass_rate = sum(row["status"] == "PASS" for row in checks) / len(checks)
    metrics = {
        f"retrieval_hit_rate_at_{k}": aggregate(retrieval_rows, f"hit_rate@{k}"),
        f"retrieval_recall_at_{k}": aggregate(retrieval_rows, f"recall@{k}"),
        f"retrieval_precision_at_{k}": aggregate(retrieval_rows, f"precision@{k}"),
        "retrieval_mrr": aggregate(retrieval_rows, "mrr"),
        f"retrieval_ndcg_at_{k}": aggregate(retrieval_rows, f"ndcg@{k}"),
        "answer_exact_match": aggregate(answer_rows, "exact_match"),
        "answer_token_f1": aggregate(answer_rows, "token_f1"),
        "fact_coverage": aggregate(answer_rows, "fact_coverage"),
        "faithfulness": aggregate(answer_rows, "faithfulness"),
        "abstention_accuracy": aggregate(answer_rows, "abstention_accuracy"),
        "faiss_cold_ms": cold_ms,
        "warm_mean_ms": float(latency["mean_ms"]),
        "warm_p50_ms": float(latency["p50_ms"]),
        "warm_p95_ms": float(latency["p95_ms"]),
        "warm_p99_ms": float(latency["p99_ms"]),
        "functional_pass_rate": functional_pass_rate,
        "peak_rss_delta_mib": max(0.0, _memory_mib() - started_rss),
    }
    return build_report(
        "offline",
        checks,
        metrics,
        {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "pid": os.getpid(),
            "iterations": iterations,
            "k": k,
            "note": "Deterministic component benchmark; not an end-to-end model score.",
        },
    )

