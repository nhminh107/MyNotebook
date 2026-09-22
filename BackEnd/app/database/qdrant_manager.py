from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, HnswConfigDiff, Batch,Filter, FieldCondition,
    MatchValue, ScalarQuantization, ScalarQuantizationConfig, ScalarType, SearchParams, Memory,
    KeywordIndexParams,
    KeywordIndexType, SparseVectorParams, Modifier, SparseVector, Prefetch, Fusion, FusionQuery)
from BackEnd.app.CONFIG import QDRANT_URL, EMBEDDING_SIZE
from BackEnd.app.database.sql_models import User, Document
from fastembed import SparseTextEmbedding
import uuid 

class QDrant:
    def __init__(self):
        self.client = QdrantClient(url=QDRANT_URL)
        self.bm25_model = SparseTextEmbedding(
            model_name="Qdrant/bm25",
            disable_stemmer=True
        )
        if not self.client.collection_exists("user_documents"):
            self.client.create_collection(
                collection_name="user_documents",
                vectors_config={
                    "dense": VectorParams(
                        size=EMBEDDING_SIZE,
                        distance=Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    "bm25": SparseVectorParams(modifier=Modifier.IDF)
                },
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

        sparse_vectors = list(self.bm25_model.embed(texts))
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
            vectors={
                "dense": embedding_vecs.tolist(),
                "bm25": [
                    SparseVector(
                        indices=sparse_vector.indices.tolist(),
                        values=sparse_vector.values.tolist(),
                    )
                    for sparse_vector in sparse_vectors
                ],
            },     
        )
        try: 
            self.client.upsert(
                collection_name="user_documents",
                points=points
            )
            return 200
        except Exception as e:
            raise e

    def search(self, user_id: str, query_text: str, query_embedding, chat_id: str, limit: int = 10, doc_id: str = None) -> str:
        conditions = [
            FieldCondition(
                key="user_id",
                match=MatchValue(value=user_id)
            )
        ]

        if doc_id:
            conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=doc_id)
                )
            )
        else:
            conditions.append(
                FieldCondition(
                    key="chat_id",
                    match=MatchValue(value=chat_id)
                )
            )

        query_filter = Filter(must=conditions)
        sparse_embedding = next(self.bm25_model.query_embed(query_text))
        sparse_query = SparseVector(
            indices=sparse_embedding.indices.tolist(),
            values=sparse_embedding.values.tolist()
        )

        result = self.client.query_points(
            collection_name="user_documents",
            prefetch=[
                Prefetch(
                    query=query_embedding.tolist(),
                    using="dense",
                    filter=query_filter,
                    params=SearchParams(hnsw_ef=128, exact=False),
                    limit=limit * 2
                ),
                Prefetch(
                    query=sparse_query,
                    using="bm25",
                    filter=query_filter,
                    limit=limit * 2
                )
            ],
            query=FusionQuery(fusion=Fusion.RRF),
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
