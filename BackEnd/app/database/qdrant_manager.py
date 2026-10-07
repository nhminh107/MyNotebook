from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, HnswConfigDiff, Batch,Filter, FieldCondition,
    MatchValue, ScalarQuantization, ScalarQuantizationConfig, ScalarType, SearchParams, Memory,
    KeywordIndexParams,
    KeywordIndexType, SparseVectorParams, Modifier, SparseVector, Prefetch, Fusion, FusionQuery)
from BackEnd.app.CONFIG import QDRANT_URL, EMBEDDING_SIZE
from BackEnd.app.database.sql_models import Chunk, Document
from BackEnd.app.retrieval_models import RetrievalHit
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
    def add(self, embedding_vecs, texts: list[str], user: str, doc: Document, chat_id: str, chunks: list[Chunk] | None = None):
        if len(embedding_vecs) != len(texts):
            raise ValueError("Embedding and chunk counts must match.")
        if chunks is not None and (len(chunks) != len(texts) or any(
            chunk.content != text or chunk.document_id != doc.document_id
            for chunk, text in zip(chunks, texts)
        )):
            raise ValueError("Chunk metadata must match document and text order.")
        ids = []
        payloads = []

        sparse_vectors = list(self.bm25_model.embed(texts))
        for index, text in enumerate(texts):
            chunk = chunks[index] if chunks is not None else None
            point_id = chunk.chunk_id if chunk else str(uuid.uuid4())
            ids.append(point_id)
            payloads.append({
                "user_id": user,
                "document_id": doc.document_id,
                "content": text,
                "chat_id": chat_id,
                "chunk_id": chunk.chunk_id if chunk else None,
                "file_name": doc.file_name,
                "page": chunk.page if chunk else None,
                "chunk_index": chunk.chunk_index if chunk else None,
                "ocr_used": chunk.ocr_used if chunk else None,
                "metadata_version": 2,
            })

        if len(set(ids)) != len(ids):
            raise ValueError("Chunk IDs must be unique within a batch.")

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

    def search_hits(self, user_id: str, query_text: str, query_embedding, chat_id: str, limit: int = 10, doc_id: str | None = None) -> list[RetrievalHit]:
        if limit < 1 or limit > 100:
            raise ValueError("Retrieval limit must be between 1 and 100.")
        conditions = [
            FieldCondition(
                key="user_id",
                match=MatchValue(value=user_id)
            ),
            FieldCondition(key="chat_id", match=MatchValue(value=chat_id)),
        ]

        if doc_id:
            conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=doc_id)
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
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
            with_vectors=False,
        )

        hits = []
        for rank, point in enumerate(result.points, start=1):
            payload = point.payload or {}
            if not payload.get("content") or not payload.get("document_id"):
                continue
            hits.append(RetrievalHit(
                chunk_id=payload.get("chunk_id"),
                qdrant_point_id=str(point.id),
                document_id=payload["document_id"],
                file_name=payload.get("file_name") or "",
                page=payload.get("page"),
                chunk_index=payload.get("chunk_index"),
                ocr_used=payload.get("ocr_used"),
                content=payload["content"],
                score=point.score,
                retrieval_rank=rank,
                metadata_version=payload.get("metadata_version", 1),
            ))
        return hits

    def search(self, user_id: str, query_text: str, query_embedding,
               chat_id: str, limit: int = 10, doc_id: str | None = None) -> str:
        """Keep the text-only contract for existing callers."""
        hits = self.search_hits(user_id, query_text, query_embedding, chat_id, limit, doc_id)
        return "\n\n".join(
            f"{index}. {hit.content}" for index, hit in enumerate(hits, start=1)
        )
