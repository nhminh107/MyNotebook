from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, HnswConfigDiff, Batch,Filter, FieldCondition,
    MatchValue, ScalarQuantization, ScalarQuantizationConfig, ScalarType, SearchParams, Memory,
    KeywordIndexParams,
    KeywordIndexType)
from BackEnd.app.CONFIG import QDRANT_URL, EMBEDDING_SIZE
from BackEnd.app.database.sql_models import User, Document
import uuid 

class QDrant:
    def __init__(self):
        self.client = QdrantClient(url=QDRANT_URL)
        if not self.client.collection_exists("user_documents"):
            self.client.create_collection(
                collection_name="user_documents",
                vectors_config=VectorParams(size=EMBEDDING_SIZE, distance=Distance.COSINE),
                hnsw_config=HnswConfigDiff(m=16, ef_construct=100),
                quantization_config=ScalarQuantization(
                    scalar=ScalarQuantizationConfig(
                        type=ScalarType.INT8,
                        quantile=0.99,
                        memory=Memory.PINNED, 
                    )
                )
            )
            self.client.create_payload_index(
                collection_name="user_documents", 
                field_name="user_id",
                field_schema=KeywordIndexParams(
                    type=KeywordIndexType.KEYWORD,
                    is_tenant=True,
                ),
            )
    def add(self, embedding_vecs, texts: list[str], user: str, doc: Document, chat_id: str):
        ids = []
        payloads = []

        for text in texts:
            ids.append(str(uuid.uuid4()))
            payloads.append({
                "user_id": user,
                "document_id": doc.document_id,
                "content": text,
                "chat_id": chat_id
            })

        points = Batch(
            ids=ids, 
            payloads=payloads, 
            vectors=embedding_vecs
        )
        try: 
            self.client.upsert(
                collection_name="user_documents",
                points=points
            )
            return 200
        except Exception as e:
            raise e

    def search(self, user_id: str, query_embedding, chat_id: str, limit: int = 10, doc_id: str = None) -> str:
        if doc_id: 
            result = self.client.query_points(
                collection_name="user_documents",
                query=query_embedding, 
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="user_id",
                            match=MatchValue(value=user_id)
                        ),
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=doc_id)
                        )
                    ]
                ), 
                search_params=SearchParams(hnsw_ef=128, exact=False),
                limit=limit
            )
        else: 
            result = self.client.query_points(
                collection_name="user_documents",
                query=query_embedding, 
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="user_id",
                            match=MatchValue(value=user_id)
                        ), 
                        FieldCondition(
                            key="chat_id", 
                            match=MatchValue(value=chat_id)
                        )
                        
                    ]
                ), 
                search_params=SearchParams(hnsw_ef=128, exact=False),
                limit=limit
            )

        contents = [
            point.payload["content"]
            for point in result.points
            if point.payload and "content" in point.payload
        ]
        return "\n\n".join(
            f"{index}. {content}"
            for index, content in enumerate(contents, start=1)
        )
