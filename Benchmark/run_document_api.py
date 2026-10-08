"""Measure authenticated RAG SSE on an explicitly prepared benchmark chat."""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import sys
import time
import tomllib
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Benchmark"))

from rag_benchmark.corpus import prepare_corpus, score_retrieval, validate_dataset
from rag_benchmark.metrics import evaluate_answer, normalize_text
from rag_benchmark.report import aggregate, build_report, check_thresholds, write_report
from rag_benchmark.timing import percentile
from BackEnd.app.retrieval_models import CITATION_PATTERN, CODE_PATTERN


def parse_stream(response) -> dict:
    """Read the app's named SSE events and retain evidence, timing and errors."""
    started = time.perf_counter()
    first_token = None
    event, tokens, sources, cited_ids, errors = "", [], [], [], []
    done = False
    for raw_line in response:
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if line.startswith("event: "):
            event = line[7:]
            done = done or event == "done"
        elif line.startswith("data: "):
            payload = json.loads(line[6:])
            if event == "token":
                content = str(payload.get("content", ""))
                if content and first_token is None:
                    first_token = time.perf_counter()
                tokens.append(content)
            elif event == "sources":
                sources = payload.get("sources", [])
            elif event == "citations":
                cited_ids = payload.get("cited_source_ids", [])
            elif event == "error":
                errors.append("SSE error event")
    # Derive markers independently so an invalid backend ID cannot get credit.
    answer = "".join(tokens)
    markers = list(dict.fromkeys(
        int(value) for value in CITATION_PATTERN.findall(CODE_PATTERN.sub("", answer))
    ))
    return {"answer": answer, "sources": sources, "cited_ids": markers,
            "backend_cited_ids": cited_ids, "done": done, "errors": errors,
            "stream_ttft_ms": (first_token - started) * 1000 if first_token else None}


def native_hits(sources: list[dict], manifest: dict) -> list[dict]:
    """Map native filename/page evidence to gold pages without guessing chunk IDs."""
    by_name = {Path(doc["path"]).name: doc["id"] for doc in manifest["documents"]}
    hits = []
    for source in sources:
        document_id = by_name.get(source.get("file_name", ""))
        page = source.get("page")
        page_id = f"{document_id}:p{page}" if document_id else "unknown"
        hits.append({"id": str(source.get("qdrant_point_id", "unknown")),
                     "page_id": page_id, "content": source.get("content", ""),
                     "citation_id": source.get("citation_id")})
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--documents-dir", type=Path, default=Path("/home/nhminh/Documents"))
    parser.add_argument("--split", choices=("dev", "test", "all"), default="test")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "Benchmark" / "results")
    args = parser.parse_args()
    if args.k < 1:
        parser.error("--k must be positive")
    with args.config.open("rb") as handle:
        config = tomllib.load(handle)["document_api"]
    username = os.environ.get("BENCHMARK_USERNAME")
    password = os.environ.get("BENCHMARK_PASSWORD")
    if not username or not password:
        parser.error("Set BENCHMARK_USERNAME and BENCHMARK_PASSWORD without placing them in the config file.")
    base_url = config["base_url"].rstrip("/")
    timeout = float(config.get("timeout_seconds", 120))
    dataset_path = ROOT / "Benchmark" / "datasets" / "document_qa.json"
    manifest = json.loads((dataset_path.parent / "documents.json").read_text())
    dataset = json.loads(dataset_path.read_text())
    _, pages, _ = prepare_corpus(manifest, args.documents_dir)
    validate_dataset(dataset, pages)
    cases = [case for case in dataset["cases"] if args.split == "all" or case["split"] == args.split]
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(path: str, payload: dict):
        return opener.open(urllib.request.Request(
            base_url + path, data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        ), timeout=timeout)

    # Never print the login response, password or session cookie.
    try:
        with request("/auth/login", {"user_name": username, "password": password}) as response:
            if response.status != 200:
                raise RuntimeError("Benchmark login failed.")
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Benchmark login failed (HTTP {exc.code}).") from None
    checks, rows, quality, latency, ttft = [], [], [], [], []
    per_case_chats = config.get("case_chat_ids", {})
    if per_case_chats and set(per_case_chats) != {case["id"] for case in cases}:
        raise SystemExit("case_chat_ids must cover exactly the selected split.")
    if per_case_chats and len(set(per_case_chats.values())) != len(per_case_chats):
        raise SystemExit("case_chat_ids must use a distinct pre-indexed chat per case.")
    for case in cases:
        started = time.perf_counter()
        try:
            with request("/documents/retrieval/stream", {
                "user_id": config["user_id"],
                "chat_id": per_case_chats.get(case["id"], config.get("chat_id", "")),
                "user_query": case["question"], "include_sources": True,
            }) as response:
                if response.headers.get_content_type() != "text/event-stream":
                    raise ValueError("Expected text/event-stream response.")
                header_ms = (time.perf_counter() - started) * 1000
                result = parse_stream(response)
            total_ms = (time.perf_counter() - started) * 1000
            hits = native_hits(result["sources"], manifest)
            scores = score_retrieval(case, hits, args.k) if case["evidence"] else {}
            answer = re.sub(r"\[\[source:[1-9]\d*\]\]", "", result["answer"])
            answer_scores = evaluate_answer(answer, case["reference_answer"], case["required_facts"], [hit["content"] for hit in hits], case["expected_abstain"])
            # Use whole normalized tokens for short facts such as option B.
            normalized_answer = f" {normalize_text(answer)} "
            facts = case["required_facts"]
            answer_scores["fact_coverage"] = sum(f" {normalize_text(fact)} " in normalized_answer for fact in facts) / len(facts) if facts else 1.0
            answer_scores["lexical_faithfulness_proxy"] = answer_scores.pop("faithfulness")
            answer_scores.pop("answer_relevancy")
            gold = {f"{e['document_id']}:p{e['page']}" for e in case["evidence"]}
            cited = result["cited_ids"]
            valid = [hit for hit in hits if hit["citation_id"] in cited and hit["page_id"] in gold]
            answer_scores["citation_page_precision"] = len(valid) / len(cited) if cited else 0.0
            answer_scores["citation_page_recall"] = len({hit["page_id"] for hit in valid}) / len(gold) if gold else 0.0
            ok = result["done"] and not result["errors"] and bool(answer.strip())
            checks.append({"name": case["id"], "status": "PASS" if ok else "FAIL", "detail": "SSE completed" if ok else "Missing done/answer or SSE error"})
            rows.append({"id": case["id"], "category": case["category"], "scores": scores, "answer_scores": answer_scores, "total_ms": total_ms, **result})
            quality.append({"negative": case["expected_abstain"], "scores": answer_scores, "retrieval": scores})
            latency.append(total_ms)
            if result["stream_ttft_ms"] is not None:
                ttft.append(header_ms + result["stream_ttft_ms"])
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            detail = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
            checks.append({"name": case["id"], "status": "FAIL", "detail": detail})
            rows.append({"id": case["id"], "error": detail})
    positive = [row["scores"] for row in quality if not row["negative"]]
    negative = [row["scores"] for row in quality if row["negative"]]
    retrieved = [row["retrieval"] for row in quality if not row["negative"]]
    metrics = {"request_success_rate": sum(check["status"] == "PASS" for check in checks) / len(cases),
               "scored_cases": len(quality), "selected_cases": len(cases),
               "total_p50_ms": percentile(latency, 0.5), "total_p95_ms": percentile(latency, 0.95),
               "ttft_p50_ms": percentile(ttft, 0.5), "ttft_p95_ms": percentile(ttft, 0.95)}
    for field in ("exact_match", "token_f1", "fact_coverage", "lexical_faithfulness_proxy", "citation_page_precision", "citation_page_recall"):
        if positive:
            metrics[f"answer_{field}"] = aggregate(positive, field)
    if negative:
        metrics["negative_abstention_accuracy"] = aggregate(negative, "abstention_accuracy")
    if retrieved:
        metrics[f"page_retrieval_recall@{args.k}"] = aggregate(retrieved, f"recall@{args.k}")
    checks.extend(check_thresholds(metrics, {
        "request_success_rate": 1.0, "answer_fact_coverage": 0.8,
        "answer_citation_page_precision": 0.8, "answer_citation_page_recall": 0.75,
        "negative_abstention_accuracy": 0.8,
    }))
    report = build_report("document-api", checks, metrics, {
        "split": args.split, "k": args.k, "base_url": base_url,
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "document_hashes": {doc["id"]: doc["sha256"] for doc in manifest["documents"]},
        "history_mode": "independent pre-indexed chats" if per_case_chats else "sequential shared chat; summary/history can affect later answers",
        "note": "Requires exactly the four manifest PDFs already indexed. Login and RAG requests write conversation history. Answer metrics exclude request exceptions; request failures fail the run. Latency is successful HTTP streams only, without cold/warm classification.",
    })
    report["cases"] = rows
    json_path, markdown_path = write_report(report, args.output_dir)
    print(f"JSON report: {json_path}\nMarkdown report: {markdown_path}")
    return int(report["status"] == "FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
