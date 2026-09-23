from __future__ import annotations

import platform
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from .metrics import evaluate_retrieval

from .live import load_jsonl
from .report import build_report, check_thresholds
from .timing import LatencyRecorder


def run_local(dataset_path: Path, iterations: int = 10, thresholds: dict[str, float] | None = None) -> dict:
    """Benchmark local model-backed components using the application's real models."""
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    checks: list[dict] = []
    metrics: dict[str, float] = {}

    # Avoid long network retries. Local suite must use the application's cached models.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    try:
        import pymupdf
        from docx import Document as WordDocument
        from BackEnd.app.doc_extractor.extractor import ExtractorFactory

        extractor_recorder = LatencyRecorder()
        schema_compatible = True
        with tempfile.TemporaryDirectory(prefix="mynotebook-extractors-") as directory:
            temp_dir = Path(directory)
            text = "MyNotebook dùng RAG. " * 80
            txt_path = temp_dir / "fixture.txt"
            txt_path.write_text(text, encoding="utf-8")
            docx_path = temp_dir / "fixture.docx"
            word = WordDocument()
            word.add_paragraph(text)
            word.save(docx_path)
            pdf_path = temp_dir / "fixture.pdf"
            pdf = pymupdf.open()
            page = pdf.new_page()
            page.insert_textbox(page.rect, text[:1500])
            pdf.save(pdf_path)
            pdf.close()

            total_chunks = 0
            for path in (txt_path, docx_path, pdf_path):
                extractor = ExtractorFactory.create(str(path))
                if extractor is None:
                    raise ValueError(f"No extractor for {path.suffix}")
                pages = extractor_recorder.measure(lambda extractor=extractor, path=path: extractor.extract(str(path)))
                schema_compatible = schema_compatible and all("texts" in page_data for page_data in pages)
                total_chunks += sum(len(page_data.get("texts", page_data.get("text", []))) for page_data in pages)
        extractor_summary = extractor_recorder.summary()
        metrics["extractor_mean_ms"] = float(extractor_summary["mean_ms"])
        metrics["extractor_p95_ms"] = float(extractor_summary["p95_ms"])
        checks.append({"name": "pdf_docx_txt_extraction", "status": "PASS", "detail": f"chunks={total_chunks}; p95={metrics['extractor_p95_ms']:.2f} ms"})
        checks.append({"name": "extractor_pipeline_schema", "status": "PASS" if schema_compatible else "FAIL", "detail": "Pipeline requires page['texts'] for every extractor"})
    except Exception as exc:
        checks.append({"name": "pdf_docx_txt_extraction", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    try:
        from BackEnd.app.text_input.Embedding import EmbeddingModel
        init_started = time.perf_counter()
        embedder = EmbeddingModel()
        cold_vector = embedder.embed_query("Benchmark cold start VietRAG embedding")
        metrics["embedding_cold_ms"] = (time.perf_counter() - init_started) * 1000
        recorder = LatencyRecorder()
        for _ in range(iterations):
            vector = recorder.measure(lambda: embedder.embed_query("Qdrant dùng RRF như thế nào?"))
            if vector.shape != cold_vector.shape:
                raise ValueError("Embedding shape changed between calls")
        summary = recorder.summary()
        metrics.update({f"embedding_warm_{key}": float(value) for key, value in summary.items() if key != "count"})
        checks.append({"name": "embedding_model", "status": "PASS", "detail": f"dimension={cold_vector.shape[0]}, iterations={iterations}"})

        import faiss

        fixture = root / "Benchmark" / "fixtures" / "benchmark_knowledge.txt"
        chunks = [part.strip() for part in fixture.read_text(encoding="utf-8").split("\n\n") if part.strip()]
        chunk_ids = [f"p{index}" for index in range(len(chunks))]
        vectors = embedder.embed_passages(chunks)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(np.ascontiguousarray(vectors, dtype=np.float32))
        retrieval_cases = [
            ("Mô hình embedding tiếng Việt là gì?", {"p0"}),
            ("Dense và BM25 được hợp nhất bằng thuật toán nào?", {"p1"}),
            ("Agent có thể dùng OCR và máy tính không?", {"p2"}),
        ]
        retrieval_scores = []
        for question, relevant in retrieval_cases:
            query = np.ascontiguousarray(embedder.embed_query(question), dtype=np.float32).reshape(1, -1)
            _, positions = index.search(query, min(3, len(chunks)))
            retrieved = [chunk_ids[position] for position in positions[0] if position >= 0]
            retrieval_scores.append(evaluate_retrieval(retrieved, relevant, min(3, len(chunks))))
        metrics["retrieval_hit_rate_at_k"] = sum(row[f"hit_rate@{min(3, len(chunks))}"] for row in retrieval_scores) / len(retrieval_scores)
        metrics["retrieval_recall_at_k"] = sum(row[f"recall@{min(3, len(chunks))}"] for row in retrieval_scores) / len(retrieval_scores)
        metrics["retrieval_mrr"] = sum(row["mrr"] for row in retrieval_scores) / len(retrieval_scores)
        checks.append({"name": "embedding_faiss_retrieval_accuracy", "status": "PASS", "detail": f"hit_rate@3={metrics['retrieval_hit_rate_at_k']:.3f}, mrr={metrics['retrieval_mrr']:.3f}"})
    except Exception as exc:
        checks.append({"name": "embedding_model", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    try:
        from BackEnd.app.query_router.router import QueryRouter
        cases = load_jsonl(dataset_path)
        init_started = time.perf_counter()
        router = QueryRouter()
        metrics["router_cold_init_ms"] = (time.perf_counter() - init_started) * 1000
        recorder = LatencyRecorder()
        correct = 0
        confusion: dict[str, int] = {}
        for case in cases:
            result = recorder.measure(lambda case=case: router.route(case["question"]))
            predicted = result["route"]
            expected = case["expected_route"]
            correct += predicted == expected
            confusion[f"{expected}->{predicted}"] = confusion.get(f"{expected}->{predicted}", 0) + 1
        summary = recorder.summary()
        metrics["router_accuracy"] = correct / len(cases) if cases else 0.0
        metrics["router_warm_p50_ms"] = float(summary["p50_ms"])
        metrics["router_warm_p95_ms"] = float(summary["p95_ms"])
        checks.append({"name": "query_router", "status": "PASS", "detail": f"accuracy={metrics['router_accuracy']:.3f}; confusion={confusion}"})
    except Exception as exc:
        checks.append({"name": "query_router", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    metrics["functional_pass_rate"] = sum(check["status"] == "PASS" for check in checks) / len(checks)
    if thresholds:
        supported = {key: value for key, value in thresholds.items() if key in metrics}
        checks.extend(check_thresholds(metrics, supported))
    return build_report("local-models", checks, metrics, {"iterations": iterations, "dataset": str(dataset_path), "python": sys.version.split()[0], "platform": platform.platform()})
