from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def aggregate(rows: list[dict[str, Any]], field: str) -> float:
    values = [float(row[field]) for row in rows if field in row]
    return sum(values) / len(values) if values else 0.0


def build_report(suite: str, checks: list[dict], metrics: dict, metadata: dict) -> dict:
    passed = sum(check.get("status") == "PASS" for check in checks)
    failed = sum(check.get("status") == "FAIL" for check in checks)
    skipped = sum(check.get("status") == "SKIP" for check in checks)
    return {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "suite": suite,
        "status": "FAIL" if failed else "PASS",
        "summary": {"passed": passed, "failed": failed, "skipped": skipped},
        "metrics": metrics,
        "checks": checks,
        "metadata": metadata,
    }


def write_report(report: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"{report['suite']}-{stamp}"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = report["summary"]
    lines = [
        f"# Benchmark report: {report['suite']}",
        "",
        f"- Status: **{report['status']}**",
        f"- Created: `{report['created_at']}`",
        f"- Checks: {summary['passed']} pass / {summary['failed']} fail / {summary['skipped']} skip",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in sorted(report["metrics"].items()):
        rendered = f"{value:.4f}" if isinstance(value, float) else str(value)
        lines.append(f"| {key} | {rendered} |")
    lines.extend(["", "## Functional checks", "", "| Feature | Status | Detail |", "|---|---|---|"])
    for check in report["checks"]:
        detail = str(check.get("detail", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {check['name']} | {check['status']} | {detail} |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def check_thresholds(metrics: dict[str, float], thresholds: dict[str, float]) -> list[dict]:
    checks = []
    for name, target in thresholds.items():
        if name not in metrics:
            checks.append({"name": f"threshold:{name}", "status": "SKIP", "detail": "Metric unavailable"})
            continue
        actual = float(metrics[name])
        lower_is_better = name.endswith("_ms")
        passed = actual <= target if lower_is_better else actual >= target
        operator = "<=" if lower_is_better else ">="
        checks.append({
            "name": f"threshold:{name}",
            "status": "PASS" if passed else "FAIL",
            "detail": f"actual={actual:.4f}, required {operator} {target:.4f}",
        })
    return checks

