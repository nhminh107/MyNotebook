import pymupdf
from abc import ABC, abstractmethod
from pathlib import Path
from BackEnd.app.doc_extractor.texts_chunking import chunking
class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: str):
        pass

class PDFExtractor(BaseExtractor):
    def extract(self, file_path):
        pages = []
        with pymupdf.open(file_path) as doc:
            for page_num, page in enumerate(doc):
                text = page.get_text("text")
                chunked_texts = chunking(text)
                pages.append({
                    "page": page_num + 1,
                    "texts": chunked_texts
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
        chunked_texts = chunking(text)
        return [{
            "page": None,
            "text": chunked_texts
        }]

class TextExtractor(BaseExtractor):

    def extract(self, file_path: str):

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        chunked_texts = chunking(text)
        return [{
            "page": None,
            "text": chunked_texts
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
