import pymupdf
from abc import ABC, abstractmethod
from pathlib import Path

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: str):
        pass

class PDFExtractor(BaseExtractor):
    def extract(self, file_path):
        doc = pymupdf.open(file_path)

        pages = []
        for page_num, page in enumerate(doc):
            pages.append({
                "page": page_num + 1,
                "text": page.get_text("text")
            })

        return pages


class WordExtractor(BaseExtractor):
    def extract(self, file_path: str):
        from docx import Document

        doc = Document(file_path)

        text = "\n".join(
            paragraph.text
            for paragraph in doc.paragraphs
        )

        return [{
            "page": None,
            "text": text
        }]

class TextExtractor(BaseExtractor):

    def extract(self, file_path: str):

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        return [{
            "page": None,
            "text": text
        }]

class ExtractorFactory:
    @staticmethod
    def create(file_path: str) -> BaseExtractor:
        extension = Path(file_path).suffix.lower()
        if extension == ".pdf": 
            return PDFExtractor()
        if extension == ".docx" or extension == ".doc" or extension == ".docs": 
            return WordExtractor()
        if extension == ".txt": 
            return TextExtractor()
