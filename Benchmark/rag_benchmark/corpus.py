"""Reproducible PDF corpus retrieval and exported RAG answer evaluation."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

from .metrics import evaluate_answer, evaluate_retrieval, normalize_text
from .report import aggregate, build_report, check_thresholds
from .timing import percentile


def read_pdf(path: Path) -> list[str]:
    """Extract text layers, retaining one-based physical PDF page boundaries."""
    executable = shutil.which("pdftotext")
    if executable is None:
        raise RuntimeError("pdftotext command not found; PDF text extraction requires Poppler.")
    result = subprocess.run(
        [executable, "-layout", "-enc", "UTF-8", str(path), "-"],
        capture_output=True, text=True, check=True, timeout=120,
    )
    pages = result.stdout.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def prepare_corpus(manifest: dict, documents_dir: Path) -> tuple[list[dict], dict, list[dict]]:
    """Verify source hashes and use the production recursive tokenizer chunker."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from BackEnd.app.doc_extractor.texts_chunking import chunking

    chunks, page_texts, sources = [], {}, []
    for source in manifest["documents"]:
        path = documents_dir / source["path"]
        if not path.resolve().is_relative_to(documents_dir.resolve()):
            raise ValueError("Document path escapes the source directory.")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != source["sha256"]:
            raise ValueError(f"Source checksum changed: {source['id']}")
        started = time.perf_counter()
        pages = read_pdf(path)
        if len(pages) != source["pages"]:
            raise ValueError(f"Page count changed: {source['id']}")
        for page, text in enumerate(pages, 1):
            page_id = f"{source['id']}:p{page}"
            page_texts[page_id] = text
            for index, content in enumerate(chunking(text)):
                chunks.append({
                    "id": f"{page_id}:c{index}", "document_id": source["id"],
                    "page": page, "page_id": page_id, "content": content,
                })
        sources.append({**source, "extraction_chunking_ms": (time.perf_counter() - started) * 1000})
    return chunks, page_texts, sources


def validate_dataset(dataset: dict, pages: dict[str, str]) -> None:
    """Reject missing evidence, duplicate IDs/questions and invalid holdout labels."""
    ids, questions = set(), set()
    if not dataset.get("cases"):
        raise ValueError("Dataset must contain cases.")
    for case in dataset["cases"]:
        question = normalize_text(case["question"])
        if not question or question in questions or case["id"] in ids:
            raise ValueError(f"Duplicate or empty case: {case['id']}")
        ids.add(case["id"])
        questions.add(question)
        if case["split"] not in {"dev", "test"}:
            raise ValueError(f"Invalid split: {case['id']}")
        if not case["reference_answer"] or not isinstance(case["required_facts"], list):
            raise ValueError(f"Invalid answer labels: {case['id']}")
        evidence = case["evidence"]
        if bool(evidence) == bool(case["expected_abstain"]):
            raise ValueError(f"Evidence/abstention conflict: {case['id']}")
        for item in evidence:
            page_id = f"{item['document_id']}:p{item['page']}"
            quote = normalize_text(item["quote"])
            if not quote or page_id not in pages or quote not in normalize_text(pages[page_id]):
                raise ValueError(f"Unverified gold quote: {case['id']} / {page_id}")


class BM25Index:
    """Dependency-free lexical baseline (k1=1.5, b=0.75), not Qdrant BM25."""

    def __init__(self, chunks: list[dict]) -> None:
        self.chunks = chunks
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.lengths = []
        for index, chunk in enumerate(chunks):
            tokens = normalize_text(chunk["content"]).split()
            self.lengths.append(len(tokens))
            for token, count in Counter(tokens).items():
                self.postings[token].append((index, count))
        self.average_length = sum(self.lengths) / max(1, len(chunks))

    def search(self, query: str, k: int) -> list[dict]:
        scores: dict[int, float] = defaultdict(float)
        for token in set(normalize_text(query).split()):
            entries = self.postings.get(token, [])
            idf = math.log(1 + (len(self.chunks) - len(entries) + 0.5) / (len(entries) + 0.5))
            for index, frequency in entries:
                length_ratio = self.lengths[index] / max(1, self.average_length)
                scores[index] += idf * frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * length_ratio))
        ranking = sorted(scores, key=lambda index: (-scores[index], self.chunks[index]["id"]))[:k]
        return [{**self.chunks[index], "score": scores[index]} for index in ranking]


class DenseIndex:
    """Production Cloudflare BGE-M3 embedding with local cosine search."""

    def __init__(self, chunks: list[dict]) -> None:
        import numpy as np
        from dotenv import load_dotenv
        from BackEnd.app.text_input.Embedding import EmbeddingModel

        load_dotenv(Path(__file__).resolve().parents[2] / "BackEnd" / ".env")
        self.np = np
        self.chunks = chunks
        self.embedder = EmbeddingModel()
        self.vectors = self.embedder.embed_passages([chunk["content"] for chunk in chunks])

    def search(self, query: str, k: int) -> list[dict]:
        scores = self.vectors @ self.embedder.embed_query(query)
        indices = self.np.argsort(-scores, kind="stable")[:k]
        return [{**self.chunks[index], "score": float(scores[index])} for index in indices]


def score_retrieval(case: dict, hits: list[dict], k: int) -> dict[str, float]:
    """Measure distinct gold pages in the first k chunks, plus quote coverage."""
    gold_pages = {f"{item['document_id']}:p{item['page']}" for item in case["evidence"]}
    # Duplicate chunks from a page consume ranks but receive credit only once.
    seen = set()
    ranked_pages = []
    for index, hit in enumerate(hits[:k]):
        page_id = hit["page_id"]
        ranked_pages.append(page_id if page_id not in seen else f"duplicate:{index}")
        seen.add(page_id)
    scores = evaluate_retrieval(ranked_pages, gold_pages, k)
    supported = sum(
        any(
            hit["page_id"] == f"{item['document_id']}:p{item['page']}"
            and normalize_text(item["quote"]) in normalize_text(hit["content"])
            for hit in hits[:k]
        ) for item in case["evidence"]
    )
    scores["evidence_coverage"] = supported / len(case["evidence"]) if case["evidence"] else 0.0
    return scores


def evaluate_predictions(cases: list[dict], predictions: list[dict], chunks: list[dict]) -> tuple[dict, list[dict]]:
    """Score complete exported runs with verified corpus chunk IDs as evidence."""
    expected = {case["id"] for case in cases}
    actual = [prediction["id"] for prediction in predictions]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("Prediction IDs must match the selected split exactly, without duplicates.")
    by_id = {prediction["id"]: prediction for prediction in predictions}
    by_chunk = {chunk["id"]: chunk for chunk in chunks}
    rows = []
    for case in cases:
        prediction = by_id[case["id"]]
        answer = prediction["answer"]
        if not isinstance(answer, str):
            raise ValueError("Prediction answer must be a string.")
        retrieved = prediction["retrieved_ids"]
        cited = prediction["cited_ids"]
        if len(retrieved) != len(set(retrieved)) or len(cited) != len(set(cited)):
            raise ValueError("Duplicate prediction chunk IDs are not allowed.")
        if any(chunk_id not in by_chunk for chunk_id in retrieved + cited):
            raise ValueError(f"Unknown prediction chunk ID: {case['id']}")
        contexts = [by_chunk[chunk_id]["content"] for chunk_id in retrieved]
        # Citation markers are transport syntax, not answer text.
        prose = re.sub(r"\[\[source:[1-9]\d*\]\]", "", answer)
        scores = evaluate_answer(prose, case["reference_answer"], case["required_facts"], contexts, case["expected_abstain"])
        normalized_answer = f" {normalize_text(prose)} "
        facts = case["required_facts"]
        scores["fact_coverage"] = sum(
            f" {normalize_text(fact)} " in normalized_answer for fact in facts
        ) / len(facts) if facts else 1.0
        scores.pop("answer_relevancy")  # Existing token-F1 alias is not an independent metric.
        scores["lexical_faithfulness_proxy"] = scores.pop("faithfulness")
        gold_pages = {f"{item['document_id']}:p{item['page']}" for item in case["evidence"]}
        supported = [chunk_id for chunk_id in cited if chunk_id in retrieved and by_chunk[chunk_id]["page_id"] in gold_pages]
        scores["citation_page_precision"] = len(supported) / len(cited) if cited else 0.0
        scores["citation_page_recall"] = len({by_chunk[c]["page_id"] for c in supported}) / len(gold_pages) if gold_pages else 0.0
        rows.append({"id": case["id"], "expected_abstain": case["expected_abstain"], "scores": scores})
    positive = [row["scores"] for row in rows if not row["expected_abstain"]]
    negative = [row["scores"] for row in rows if row["expected_abstain"]]
    metrics = {f"answer_{field}": aggregate(positive, field) for field in (
        "exact_match", "token_f1", "fact_coverage", "lexical_faithfulness_proxy",
        "citation_page_precision", "citation_page_recall",
    )} if positive else {}
    if negative:
        metrics["negative_abstention_accuracy"] = aggregate(negative, "abstention_accuracy")
    if positive:
        metrics["positive_non_abstention_accuracy"] = aggregate(positive, "abstention_accuracy")
    return metrics, rows


def run_corpus(manifest_path: Path, dataset_path: Path, documents_dir: Path,
               split: str = "test", backend: str = "bm25", k: int = 5,
               iterations: int = 3, predictions_path: Path | None = None,
               workspace: Path | None = None) -> dict:
    """Validate, index, evaluate and retain per-question evidence for inspection."""
    if k < 1 or iterations < 1:
        raise ValueError("k and iterations must be positive.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    started = time.perf_counter()
    chunks, pages, sources = prepare_corpus(manifest, documents_dir)
    validate_dataset(dataset, pages)
    preparation_ms = (time.perf_counter() - started) * 1000
    cases = [case for case in dataset["cases"] if split == "all" or case["split"] == split]
    if not cases:
        raise ValueError("No cases in the selected split.")
    checks = [{"name": "source_hashes_and_gold_evidence", "status": "PASS", "detail": f"{len(sources)} documents, {len(pages)} pages, {len(dataset['cases'])} cases verified"}]
    metrics = {"documents": len(sources), "pages": len(pages), "chunks": len(chunks),
               "selected_cases": len(cases), "corpus_preparation_ms": preparation_ms}
    rows, answer_rows = [], []
    if predictions_path:
        predictions = json.loads(predictions_path.read_text(encoding="utf-8"))
        answer_metrics, answer_rows = evaluate_predictions(cases, predictions, chunks)
        metrics.update(answer_metrics)
        by_id = {prediction["id"]: prediction for prediction in predictions}
        by_chunk = {chunk["id"]: chunk for chunk in chunks}
        for case in cases:
            hits = [by_chunk[chunk_id] for chunk_id in by_id[case["id"]]["retrieved_ids"][:k]]
            scores = score_retrieval(case, hits, k) if case["evidence"] else {}
            rows.append({"id": case["id"], "category": case["category"], "hits": hits, "scores": scores})
        checks.append({"name": "exported_rag_predictions", "status": "PASS", "detail": "Complete prediction IDs and corpus evidence verified; execution provenance is supplied externally"})
    else:
        started = time.perf_counter()
        index = BM25Index(chunks) if backend == "bm25" else DenseIndex(chunks)
        metrics["index_build_ms"] = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        index.search(cases[0]["question"], k)
        metrics["first_query_ms"] = (time.perf_counter() - started) * 1000
        index.search(cases[0]["question"], k)  # Excluded warm-up.
        latencies = []
        wall_started = time.perf_counter()
        for _ in range(iterations):
            for case in cases:
                started = time.perf_counter()
                hits = index.search(case["question"], k)
                latencies.append((time.perf_counter() - started) * 1000)
                if _ == 0:
                    scores = score_retrieval(case, hits, k) if case["evidence"] else {}
                    rows.append({"id": case["id"], "category": case["category"], "hits": hits, "scores": scores})
        wall_seconds = time.perf_counter() - wall_started
        metrics.update({"warm_mean_ms": sum(latencies) / len(latencies),
                        "warm_p50_ms": percentile(latencies, 0.5),
                        "warm_p95_ms": percentile(latencies, 0.95),
                        "warm_p99_ms": percentile(latencies, 0.99),
                        "sequential_throughput_qps": len(latencies) / wall_seconds})
        checks.append({"name": "rag_answer_generation", "status": "SKIP", "detail": "Retrieval-only run; supply --predictions for answer/citation scoring"})
    positive = [row["scores"] for row in rows if row["scores"]]
    for field in (f"hit_rate@{k}", f"recall@{k}", f"precision@{k}", "mrr", f"ndcg@{k}", "evidence_coverage"):
        metrics[f"page_retrieval_{field}"] = aggregate(positive, field)
    breakdown = {}
    for category in sorted({row["category"] for row in rows if row["scores"]}):
        selected = [row["scores"] for row in rows if row["category"] == category]
        breakdown[category] = {"cases": len(selected), "recall": aggregate(selected, f"recall@{k}"), "mrr": aggregate(selected, "mrr")}
    checks.extend(check_thresholds(metrics, {f"page_retrieval_recall@{k}": 0.75}))
    if workspace:
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    report = build_report("corpus", checks, metrics, {
        "backend": "external_predictions" if predictions_path else backend,
        "split": split, "k": k, "iterations": iterations,
        "dataset_version": dataset["version"],
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "extractor": "pdftotext -layout; text layers only; no OCR",
        "chunker": "production recursive multilingual-e5-base tokenizer, 400 tokens, overlap 60",
        "sources": sources, "category_breakdown": breakdown,
        "quality_population": "Positive cases only for retrieval/answer; negatives separately for abstention",
        "limitations": "Page relevance is weaker than exact evidence; quote coverage is stricter. No semantic judge, Qdrant hybrid, tenant isolation, or live TTFT measured.",
    })
    report["cases"] = rows
    report["answer_cases"] = answer_rows
    return report
