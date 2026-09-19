"""Inspect token-split output from PDFExtractor on a complete PDF book."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from BackEnd.app.doc_extractor.extractor import PDFExtractor


DEFAULT_PDF_PATH = Path(
    "/home/nhminh/Downloads/Hands-On-Large-Language-Models.pdf"
)


def _print_result(
    *,
    pdf_path: Path,
    page_count: int,
    elapsed_seconds: float,
    first_content_page: dict[str, Any],
) -> None:
    """Print execution time and the first non-empty page output."""
    print("\nPDFExtractor token-split benchmark")
    print(f"PDF: {pdf_path}")
    print(f"Pages processed: {page_count}")
    print(f"Execution time: {elapsed_seconds:.6f} seconds")
    print("\nComplete first non-empty page output")
    print(json.dumps(first_content_page, ensure_ascii=False, indent=2))


def test_extract_book_and_print_first_page() -> None:
    """Process the book and print all output from its first non-empty page."""
    pdf_path = Path(
        os.environ.get("PDF_EXTRACTOR_TEST_PDF", str(DEFAULT_PDF_PATH))
    ).expanduser()
    assert pdf_path.is_file(), f"Test PDF does not exist: {pdf_path}"

    started_at = time.perf_counter()
    output = PDFExtractor().extract(str(pdf_path))
    elapsed_seconds = time.perf_counter() - started_at

    assert isinstance(output, list)
    assert output, "PDFExtractor returned no pages"
    assert [item["page"] for item in output] == list(
        range(1, len(output) + 1)
    )
    assert all(isinstance(item["texts"], list) for item in output)
    assert all(
        isinstance(chunk, str)
        for item in output
        for chunk in item["texts"]
    )

    first_content_page = next(
        (
            item
            for item in output
            if any(chunk.strip() for chunk in item["texts"])
        ),
        None,
    )
    assert first_content_page is not None, "PDFExtractor returned no text"

    _print_result(
        pdf_path=pdf_path,
        page_count=len(output),
        elapsed_seconds=elapsed_seconds,
        first_content_page=first_content_page,
    )
