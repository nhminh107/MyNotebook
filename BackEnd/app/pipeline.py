from collections.abc import Iterator
from pathlib import Path
import uuid

import BackEnd.app.CONFIG
from BackEnd.app.chatbot.chatbot import Chatbot
from BackEnd.app.database.qdrant_manager import QDrant
from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.database.sql_models import Chunk, Document, User
from BackEnd.app.doc_extractor.extractor import (
    BaseExtractor,
    ExtractorFactory,
    PDFExtractor,
    TextExtractor,
    WordExtractor,
)
from BackEnd.app.text_input.Embedding import EmbeddingModel

class Pipeline:
    def __init__(self, sql: Supabase_Manager, qdrant: QDrant, embedding_model: EmbeddingModel, chatbot: Chatbot = None):
        self.sql = sql
        self.qdrant = qdrant
        self.embedding_model = embedding_model
        self.chatbot = chatbot

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
        chunks = []

        for page in document_chunks:
            for text in page["texts"]:
                chunk = Chunk(
                    chunk_id=str(uuid.uuid4()),
                    document_id=doc.document_id,
                    content=text,
                )
                chunks.append(chunk)

                if len(chunks) >= 200:
                    self.sql.insert_chunks(chunks=chunks)

                    texts = [chunk.content for chunk in chunks]
                    embedding_vectors = self.embedding_model.embed_passages(texts=texts)

                    self.qdrant.add(
                        embedding_vecs=embedding_vectors,
                        texts=texts,
                        user=user_id,
                        doc=doc,
                    )

                    chunks = []

        if chunks:
            self.sql.insert_chunks(chunks=chunks)

            texts = [chunk.content for chunk in chunks]
            embedding_vectors = self.embedding_model.embed_passages(texts=texts)

            self.qdrant.add(
                embedding_vecs=embedding_vectors,
                texts=texts,
                user=user_id,
                doc=doc,
            )

    def query(self, user_id: str, user_query: str):
        query_embedding = self.embedding_model.embed_query(user_query)
        query_retrieval = self.qdrant.search(user_id=user_id, query_embedding=query_embedding)
        result = self.chatbot.invoke(user_prompt=user_query, data=query_retrieval)
        return result

    def query_stream(self, user_id: str, user_query: str) -> Iterator[str]:
        query_embedding = self.embedding_model.embed_query(user_query)
        query_retrieval = self.qdrant.search(
            user_id=user_id,
            query_embedding=query_embedding,
        )
        yield from self.chatbot.stream(
            user_prompt=user_query,
            data=query_retrieval,
        )
