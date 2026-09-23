from __future__ import annotations

import concurrent.futures
import json
import platform
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from .metrics import evaluate_answer
from .report import aggregate, build_report, check_thresholds
from .timing import percentile


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return rows


class ApiClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, payload: dict | None = None, headers: dict | None = None) -> tuple[int, bytes]:
        body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        request = urllib.request.Request(self.base_url + path, data=body, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except urllib.error.URLError as exc:
            return 0, str(exc.reason).encode()

    def stream(self, path: str, payload: dict) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode()
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            method="POST",
        )
        started = time.perf_counter()
        first_token_at = None
        tokens: list[str] = []
        events: list[str] = []
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            event = ""
            for raw_line in response:
                line = raw_line.decode("utf-8").rstrip("\r\n")
                if line.startswith("event: "):
                    event = line[7:]
                    events.append(event)
                elif line.startswith("data: ") and event == "token":
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    tokens.append(str(json.loads(line[6:]).get("content", "")))
        ended = time.perf_counter()
        return {
            "answer": "".join(tokens),
            "events": events,
            "ttft_ms": ((first_token_at or ended) - started) * 1000,
            "total_ms": (ended - started) * 1000,
            "token_chunks": len(tokens),
        }


def _multipart_upload(client: ApiClient, path: Path, user_id: str, chat_id: str) -> tuple[int, bytes]:
    boundary = f"----ragbenchmark{uuid.uuid4().hex}"
    parts = []
    for name, value in (("user_id", user_id), ("chat_id", chat_id)):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: text/plain\r\n\r\n".encode()
        + path.read_bytes()
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        client.base_url + "/documents/upload",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=client.timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        return 0, str(exc.reason).encode()


def run_live(config: dict, dataset_path: Path, iterations: int, concurrency: int, skip_upload: bool, include_auth: bool) -> dict:
    live = config.get("live", {})
    thresholds = config.get("thresholds", {})
    client = ApiClient(live.get("base_url", "http://127.0.0.1:8000"), float(live.get("request_timeout_seconds", 120)))
    user_id = str(live.get("user_id", "benchmark-user"))
    chat_id = f"{live.get('chat_id_prefix', 'benchmark')}-{int(time.time())}"
    cases = load_jsonl(dataset_path)
    checks: list[dict] = []

    status, body = client.request("GET", "/health")
    checks.append({"name": "api_health", "status": "PASS" if status == 200 else "FAIL", "detail": f"HTTP {status}: {body[:200].decode(errors='replace')}"})
    if status != 200:
        checks.extend(
            {"name": name, "status": "SKIP", "detail": "API health check failed"}
            for name in (
                "request_validation",
                "document_upload",
                "auth_register_login",
                "rag_sse_end_to_end",
                "conversation_history",
                "agent_tools_stream",
            )
        )
        return build_report(
            "live",
            checks,
            {"functional_pass_rate": 0.0},
            {"base_url": client.base_url, "dataset": str(dataset_path), "iterations": iterations, "concurrency": concurrency},
        )

    invalid_status, _ = client.request("POST", "/documents/retrieval/stream", {"user_id": user_id, "chat_id": chat_id, "user_query": ""})
    checks.append({"name": "request_validation", "status": "PASS" if invalid_status == 422 else "FAIL", "detail": f"empty query returned HTTP {invalid_status}"})

    fixture = Path(live.get("upload_fixture", "Benchmark/fixtures/benchmark_knowledge.txt"))
    if not fixture.is_absolute():
        fixture = Path(__file__).resolve().parents[2] / fixture
    if skip_upload:
        checks.append({"name": "document_upload", "status": "SKIP", "detail": "--skip-upload"})
    elif not fixture.exists():
        checks.append({"name": "document_upload", "status": "FAIL", "detail": f"fixture not found: {fixture}"})
    else:
        upload_started = time.perf_counter()
        upload_status, upload_body = _multipart_upload(client, fixture, user_id, chat_id)
        upload_ms = (time.perf_counter() - upload_started) * 1000
        checks.append({"name": "document_upload", "status": "PASS" if upload_status == 200 else "FAIL", "detail": f"HTTP {upload_status}, {upload_ms:.2f} ms: {upload_body[:300].decode(errors='replace')}"})

    auth_name = f"benchmark-{uuid.uuid4().hex[:12]}"
    if include_auth:
        register_status, _ = client.request("POST", "/auth/register", {"user_name": auth_name, "password": "Benchmark-Only-Password-937!"})
        login_status, _ = client.request("POST", "/auth/login", {"user_name": auth_name, "password": "Benchmark-Only-Password-937!"})
        checks.append({"name": "auth_register_login", "status": "PASS" if (register_status, login_status) == (200, 200) else "FAIL", "detail": f"register={register_status}, login={login_status}"})
    else:
        checks.append({"name": "auth_register_login", "status": "SKIP", "detail": "Enable with --include-auth (writes a benchmark user)"})

    rag_cases = [case for case in cases if case.get("mode") in {"rag", "negative_query"}]
    agent_cases = [case for case in cases if case.get("mode") == "agent"]
    warmups = int(live.get("warmup_runs", 1))
    cold_result = None
    warmup_latencies = []
    for case in rag_cases[:1]:
        cold_result = client.stream("/documents/retrieval/stream", {"user_id": user_id, "chat_id": chat_id, "user_query": case["question"]})
        for _ in range(warmups):
            warmup = client.stream("/documents/retrieval/stream", {"user_id": user_id, "chat_id": chat_id, "user_query": case["question"]})
            warmup_latencies.append(float(warmup["total_ms"]))

    jobs = [(case, run) for run in range(iterations) for case in rag_cases]
    wall_started = time.perf_counter()
    def execute(job):
        case, _ = job
        result = client.stream("/documents/retrieval/stream", {"user_id": user_id, "chat_id": chat_id, "user_query": case["question"]})
        scores = evaluate_answer(result["answer"], case.get("reference_answer", ""), case.get("required_facts", []), [fixture.read_text(encoding="utf-8")] if fixture.exists() else [], bool(case.get("expected_abstain")))
        return case, result, scores

    completed = []
    if jobs:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
            completed = list(executor.map(execute, jobs))
    wall_seconds = time.perf_counter() - wall_started

    result_rows = [item[1] for item in completed]
    score_rows = [item[2] for item in completed]
    total_latencies = [float(row["total_ms"]) for row in result_rows]
    ttfts = [float(row["ttft_ms"]) for row in result_rows]
    sse_ok = all("token" in row["events"] and "done" in row["events"] for row in result_rows) if result_rows else False
    checks.append({"name": "rag_sse_end_to_end", "status": "PASS" if sse_ok else "FAIL", "detail": f"{len(completed)} measured requests"})

    history_status, _ = client.request("GET", f"/documents/chats/{user_id}/{chat_id}")
    checks.append({"name": "conversation_history", "status": "PASS" if history_status == 200 else "FAIL", "detail": f"HTTP {history_status}"})

    if agent_cases:
        try:
            agent_result = client.stream("/documents/retrieval/agent-stream", {"user_id": user_id, "chat_id": chat_id, "user_query": agent_cases[0]["question"]})
            agent_ok = "done" in agent_result["events"] and "error" not in agent_result["events"]
            checks.append({"name": "agent_tools_stream", "status": "PASS" if agent_ok else "FAIL", "detail": f"events={agent_result['events']}, latency={agent_result['total_ms']:.2f} ms"})
        except Exception as exc:
            checks.append({"name": "agent_tools_stream", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})
    else:
        checks.append({"name": "agent_tools_stream", "status": "SKIP", "detail": "No agent case in dataset"})

    metrics = {
        "answer_exact_match": aggregate(score_rows, "exact_match"),
        "answer_token_f1": aggregate(score_rows, "token_f1"),
        "fact_coverage": aggregate(score_rows, "fact_coverage"),
        "faithfulness": aggregate(score_rows, "faithfulness"),
        "answer_relevancy": aggregate(score_rows, "answer_relevancy"),
        "abstention_accuracy": aggregate(score_rows, "abstention_accuracy"),
        "cold_request_ms": float(cold_result["total_ms"]) if cold_result else 0.0,
        "warmup_mean_ms": sum(warmup_latencies) / len(warmup_latencies) if warmup_latencies else 0.0,
        "warm_mean_ms": sum(total_latencies) / len(total_latencies) if total_latencies else 0.0,
        "warm_p50_ms": percentile(total_latencies, 0.50),
        "warm_p95_ms": percentile(total_latencies, 0.95),
        "warm_p99_ms": percentile(total_latencies, 0.99),
        "ttft_p50_ms": percentile(ttfts, 0.50),
        "ttft_p95_ms": percentile(ttfts, 0.95),
        "throughput_qps": len(completed) / wall_seconds if wall_seconds else 0.0,
    }
    non_skipped = [check for check in checks if check["status"] != "SKIP"]
    metrics["functional_pass_rate"] = sum(check["status"] == "PASS" for check in non_skipped) / len(non_skipped) if non_skipped else 0.0
    checks.extend(check_thresholds(metrics, thresholds))
    return build_report("live", checks, metrics, {"base_url": client.base_url, "user_id": user_id, "chat_id": chat_id, "dataset": str(dataset_path), "iterations": iterations, "concurrency": concurrency, "platform": platform.platform()})
