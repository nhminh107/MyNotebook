from abc import ABC, abstractmethod
from collections import Counter
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unicodedata

import pymupdf

from BackEnd.app.doc_extractor.texts_chunking import chunking

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: str):
        pass

class PDFExtractor(BaseExtractor):

    MIN_TEXT_LENGTH = 40
    MIN_ALPHA_RATIO = 0.35
    HEADER_FOOTER_THRESHOLD = 0.6

    def extract(self, doc_path: str | Path) -> list[dict]:
        doc_path = Path(doc_path)
        if not doc_path.is_file():
            raise FileNotFoundError(f"PDF file was not found: {doc_path}")

        raw_pages: list[dict] = []
        with pymupdf.open(doc_path) as document:
            for page_number, page in enumerate(document, start=1):
                text = self._extract_page_text(page)
                ocr_used = False
                if self._is_bad_text(text):
                    ocr_text = self._ocr_page(page)
                    if ocr_text.strip():
                        text = ocr_text
                        ocr_used = True

                raw_pages.append(
                    {
                        "page": page_number,
                        "text": text,
                        "ocr_used": ocr_used,
                    }
                )

        repeated_lines = self._find_repeated_headers_footers(raw_pages)
        results: list[dict] = []

        for page_info in raw_pages:
            text = self._remove_headers_footers(page_info["text"], repeated_lines)
            text = self._sanitize_text(text)
            results.append(
                {
                    "page": page_info["page"],
                    "texts": chunking(text) if text else [],
                    "ocr_used": page_info["ocr_used"],
                }
            )

        return results

    def _extract_page_text(self, page) -> str:
        blocks = page.get_text("blocks", sort=True)
        return "\n".join(
            str(block[4]).strip()
            for block in blocks
            if len(block) >= 5 and str(block[4]).strip()
        )

    def _is_bad_text(self, text: str) -> bool:
        """Identify scan/image pages and pages with unusable text layers."""
        compact_text = re.sub(r"\s+", "", text)
        if len(compact_text) < self.MIN_TEXT_LENGTH:
            return True
        alphabetic_count = sum(character.isalpha() for character in compact_text)
        return alphabetic_count / len(compact_text) < self.MIN_ALPHA_RATIO

    def _find_repeated_headers_footers(self, pages: list[dict]) -> set[str]:
        if len(pages) < 3:
            return set()

        candidates: list[str] = []
        for page in pages:
            lines = [line.strip() for line in page["text"].splitlines() if line.strip()]
            candidates.extend(lines[:2])
            candidates.extend(lines[-2:])

        minimum_occurrences = max(2, round(len(pages) * self.HEADER_FOOTER_THRESHOLD))
        counts = Counter(self._normalise_repeated_line(line) for line in candidates)
        return {
            line
            for line, count in counts.items()
            if line and count >= minimum_occurrences
        }

    def _remove_headers_footers(self, text: str, repeated_lines: set[str]) -> str:
        kept_lines = []
        for line in text.splitlines():
            normalized_line = self._normalise_repeated_line(line)
            if normalized_line in repeated_lines or self._is_page_number(line):
                continue
            kept_lines.append(line)
        return "\n".join(kept_lines)

    @staticmethod
    def _normalise_repeated_line(line: str) -> str:
        line = unicodedata.normalize("NFKC", line).casefold().strip()
        line = re.sub(r"\d+", "#", line)
        return re.sub(r"\s+", " ", line)

    @staticmethod
    def _is_page_number(line: str) -> bool:
        return bool(re.fullmatch(r"\s*(?:page\s*)?\d+\s*", line, flags=re.IGNORECASE))

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Repair common extraction artifacts while preserving Vietnamese Unicode."""
        text = unicodedata.normalize("NFC", text).replace("\x00", "").replace("\u00ad", "")
        text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
        text = "".join(
            character
            for character in text
            if character in "\n\t" or unicodedata.category(character)[0] != "C"
        )
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _ocr_page(self, page) -> str:

        try:

            import pytesseract
            from PIL import Image
        except ImportError:
            return ""

        try:
            pixmap = page.get_pixmap(
                dpi=300,
                alpha=False,
            )
            image = Image.frombytes(
                "RGB",
                [pixmap.width, pixmap.height],
                pixmap.samples,
            )
            try:
                return pytesseract.image_to_string(image, lang="vie+eng")
            except Exception:
                return pytesseract.image_to_string(image, lang="eng")
        except Exception:
            return ""


class WordExtractor(BaseExtractor):
    def extract(self, file_path: str):
        from docx import Document

        doc = Document(file_path)

        text = "\n".join(
            paragraph.text
            for paragraph in doc.paragraphs
        )
        chunked_texts = chunking(text)
        return [{
            "page": None,
            "texts": chunked_texts
        }]


class PowerPointExtractor(BaseExtractor):
    CONVERSION_TIMEOUT_SECONDS = 120

    def __init__(self, pdf_extractor: PDFExtractor | None = None) -> None:
        self.pdf_extractor = pdf_extractor or PDFExtractor()

    def extract(self, file_path: str | Path) -> list[dict]:
        presentation_path = Path(file_path)
        if not presentation_path.is_file():
            raise FileNotFoundError(f"PowerPoint file was not found: {presentation_path}")

        with tempfile.TemporaryDirectory(prefix="ppt-to-pdf-") as output_directory:
            pdf_path = self._convert_to_pdf(presentation_path, Path(output_directory))
            return self.pdf_extractor.extract(pdf_path)

    def _convert_to_pdf(self, presentation_path: Path, output_directory: Path) -> Path:
        libreoffice = self._find_libreoffice()
        command = [
            libreoffice,
            "--headless",
            "--convert-to",
            "pdf:impress_pdf_Export",
            "--outdir",
            str(output_directory),
            str(presentation_path),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.CONVERSION_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("PowerPoint-to-PDF conversion timed out.") from error

        pdf_path = output_directory / f"{presentation_path.stem}.pdf"
        if result.returncode != 0 or not pdf_path.is_file():
            details = (result.stderr or result.stdout).strip()
            raise RuntimeError(
                "Could not convert PowerPoint to PDF with LibreOffice. "
                f"{details or 'No PDF was produced.'}"
            )
        return pdf_path

    @staticmethod
    def _find_libreoffice() -> str:
        configured_path = os.environ.get("LIBREOFFICE_PATH")
        if configured_path and Path(configured_path).is_file():
            return configured_path

        for command in ("soffice", "libreoffice"):
            executable = shutil.which(command)
            if executable:
                return executable

        raise RuntimeError(
            "LibreOffice was not found. Install LibreOffice and add `soffice` to PATH, "
            "or set LIBREOFFICE_PATH to the full path of soffice.exe."
        )

class TextExtractor(BaseExtractor):

    def extract(self, file_path: str):

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        chunked_texts = chunking(text)
        return [{
            "page": None,
            "texts": chunked_texts
        }]

class ExtractorFactory:
    @staticmethod
    def create(file_path: str) -> BaseExtractor:
        extension = Path(file_path).suffix.lower()
        if extension == ".pdf": 
            return PDFExtractor()
        if extension in {".ppt", ".pptx"}:
            return PowerPointExtractor()
        if extension == ".docx" or extension == ".doc" or extension == ".docs": 
            return WordExtractor()
        if extension == ".txt": 
            return TextExtractor()
