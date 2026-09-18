"""Integration and performance test for :class:`PDFExtractor`."""

from __future__ import annotations

import json
import os
import resource
import time
from pathlib import Path
from typing import Any

from BackEnd.app.doc_extractor.extractor import PDFExtractor


DEFAULT_PDF_PATH = Path(
    "/home/nhminh/Downloads/Hands-On-Large-Language-Models.pdf"
)
TOP_OUTPUT_COUNT = 100
BYTES_PER_MIB = 1024 * 1024


def _current_rss_bytes() -> int:
    """Return this process's current resident set size on Linux."""
    status_path = Path("/proc/self/status")
    for line in status_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024

    raise RuntimeError("VmRSS was not found in /proc/self/status")


def _peak_rss_bytes() -> int:
    """Return peak resident memory for this process on Linux."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_maxrss * 1024


def _mib(byte_count: int) -> float:
    return byte_count / BYTES_PER_MIB


def _print_benchmark_report(
    *,
    pdf_path: Path,
    output: list[dict[str, Any]],
    elapsed_seconds: float,
    rss_before_bytes: int,
    rss_after_bytes: int,
    peak_rss_bytes: int,
) -> None:
    """Print benchmark metrics and the first 100 extracted page records."""
    report = {
        "pdf_path": str(pdf_path),
        "page_count": len(output),
        "elapsed_seconds": round(elapsed_seconds, 6),
        "rss_before_mib": round(_mib(rss_before_bytes), 3),
        "rss_after_mib": round(_mib(rss_after_bytes), 3),
        "rss_delta_mib": round(_mib(rss_after_bytes - rss_before_bytes), 3),
        "peak_rss_mib": round(_mib(peak_rss_bytes), 3),
        "top_output_count": min(TOP_OUTPUT_COUNT, len(output)),
    }

    print("\nPDFExtractor benchmark")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\nTop 100 output records")
    print(
        json.dumps(
            output[:TOP_OUTPUT_COUNT],
            ensure_ascii=False,
            indent=2,
        )
    )


def test_extract_hands_on_large_language_models() -> None:
    """Extract the sample book and report runtime, memory, and top output."""
    pdf_path = Path(
        os.environ.get("PDF_EXTRACTOR_TEST_PDF", str(DEFAULT_PDF_PATH))
    ).expanduser()
    assert pdf_path.is_file(), f"Test PDF does not exist: {pdf_path}"

    rss_before_bytes = _current_rss_bytes()
    started_at = time.perf_counter()
    output = PDFExtractor().extract(str(pdf_path))
    elapsed_seconds = time.perf_counter() - started_at
    rss_after_bytes = _current_rss_bytes()
    peak_rss_bytes = max(
        _peak_rss_bytes(),
        rss_before_bytes,
        rss_after_bytes,
    )

    assert isinstance(output, list)
    assert len(output) >= TOP_OUTPUT_COUNT
    assert [item["page"] for item in output] == list(
        range(1, len(output) + 1)
    )
    assert all(isinstance(item["text"], str) for item in output)
    assert any(item["text"].strip() for item in output)

    _print_benchmark_report(
        pdf_path=pdf_path,
        output=output,
        elapsed_seconds=elapsed_seconds,
        rss_before_bytes=rss_before_bytes,
        rss_after_bytes=rss_after_bytes,
        peak_rss_bytes=peak_rss_bytes,
    )
