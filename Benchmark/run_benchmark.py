#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path


BENCHMARK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCHMARK_DIR.parent
for path in (str(BENCHMARK_DIR), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from rag_benchmark.live import run_live
from rag_benchmark.local import run_local
from rag_benchmark.offline import run_offline
from rag_benchmark.report import write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MyNotebook RAG quality and performance benchmark")
    parser.add_argument("suite", choices=("offline", "local", "live"))
    parser.add_argument("--config", type=Path, default=BENCHMARK_DIR / "config.example.toml")
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output-dir", type=Path, default=BENCHMARK_DIR / "results")
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--include-auth", action="store_true")
    parser.add_argument("--fail-on-threshold", action="store_true")
    return parser.parse_args()


def load_config(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def main() -> int:
    args = parse_args()
    if args.iterations is not None and args.iterations < 1:
        raise SystemExit("--iterations must be at least 1")
    if args.concurrency is not None and args.concurrency < 1:
        raise SystemExit("--concurrency must be at least 1")

    if args.suite == "offline":
        report = run_offline(iterations=args.iterations or 50, k=args.k)
    elif args.suite == "local":
        dataset = args.dataset or BENCHMARK_DIR / "datasets" / "router_eval.jsonl"
        config = load_config(args.config)
        report = run_local(dataset, iterations=args.iterations or 10, thresholds=config.get("thresholds", {}))
    else:
        config = load_config(args.config)
        live = config.get("live", {})
        dataset = args.dataset or BENCHMARK_DIR / "datasets" / "live_rag.jsonl"
        report = run_live(
            config,
            dataset,
            iterations=args.iterations or int(live.get("iterations", 5)),
            concurrency=args.concurrency or int(live.get("concurrency", 1)),
            skip_upload=args.skip_upload,
            include_auth=args.include_auth,
        )

    json_path, markdown_path = write_report(report, args.output_dir)
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    if args.fail_on_threshold and report["status"] == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
