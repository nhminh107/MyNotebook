import BackEnd.app.CONFIG
from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.database.qdrant_manager import QDrant
from BackEnd.app.text_input.Embedding import EmbeddingModel
from BackEnd.app.doc_extractor.extractor import (ExtractorFactory, PDFExtractor, WordExtractor
                                                 , TextExtractor, BaseExtractor)
from BackEnd.app.database.sql_models import User, Document, Chunk
import uuid
from pathlib import Path

class Pipeline:
    def __init__(self, sql: Supabase_Manager, qdrant: QDrant, embedding_model: EmbeddingModel):
        self.sql = sql
        self.qdrant = qdrant
        self.embedding_model = embedding_model

    def insert_doc_pipeline(self, doc_path: str, user_id: str): 

        factory = ExtractorFactory()
        base_model = factory.create(doc_path)

        extension = Path(doc_path).suffix.lower()
        doc = Document(document_id=str(uuid.uuid4()), user_id=user_id, type=extension)
        self.sql.insert_document(doc=doc)

        document_chunks = base_model.extract(doc_path)
        """
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
                """
        for page in document_chunks: 
            chunks = []
            for text in page["texts"]: 
                chunk = Chunk(chunk_id=str(uuid.uuid4()), document_id=doc.document_id, content=text)
                chunks.append(chunk)

            self.sql.insert_chunks(chunks=chunks)
            texts = [chunk.content for chunk in chunks]
            embedding_vector = self.embedding_model.embed_passages(texts=texts)

            self.qdrant.add(embedding_vecs=embedding_vector, user=user_id, doc=doc)




