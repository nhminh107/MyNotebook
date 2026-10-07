from collections.abc import Iterator
from pathlib import Path
import uuid
from time import perf_counter

from BackEnd.app.retrieval_models import (
    CITATION_INSTRUCTIONS, PipelineEvent, SourceRegistry,
    format_retrieval_context, validate_citations,
)

from BackEnd.app.chatbot.chatbot import Chatbot
from BackEnd.app.database.qdrant_manager import QDrant
from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.database.sql_models import Chunk, Document, User
from BackEnd.app.chatbot.agents import Agents
from BackEnd.app.doc_extractor.extractor import (
    BaseExtractor,
    ExtractorFactory,
    PDFExtractor,
    TextExtractor,
    WordExtractor,
)
from BackEnd.app.text_input.Embedding import EmbeddingModel

class Pipeline:
    def __init__(self, sql: Supabase_Manager, qdrant: QDrant, embedding_model: EmbeddingModel, chatbot: Chatbot = None, agent: Agents = None):
        self.sql = sql
        self.qdrant = qdrant
        self.embedding_model = embedding_model
        self.chatbot = chatbot
        self.agent = agent

    def insert_doc_pipeline(self, doc_path: str, user_id: str, chat_id: str, file_name: str):

        if not self.sql.select_chat_history(user_id=user_id, chat_id=chat_id):
            self.sql.init_chat_history(chat_id=chat_id, user_id=user_id)

        factory = ExtractorFactory()
        base_model = factory.create(doc_path)

        extension = Path(doc_path).suffix.lower()
        doc = Document(
            document_id=str(uuid.uuid4()),
            user_id=user_id,
            type=extension,
            chat_id=chat_id,
            file_name=file_name
        )
        self.sql.insert_document(doc=doc)

        document_chunks = base_model.extract(doc_path)
        chunks = []
        chunk_index = 0

        for page in document_chunks:
            for text in page["texts"]:
                chunk = Chunk(
                    chunk_id=str(uuid.uuid4()),
                    document_id=doc.document_id,
                    content=text,
                    page=page.get("page"),
                    chunk_index=chunk_index,
                    ocr_used=page.get("ocr_used"),
                )
                chunks.append(chunk)
                chunk_index += 1

                if len(chunks) >= 200:
                    self.sql.insert_chunks(chunks=chunks)

                    texts = [chunk.content for chunk in chunks]
                    embedding_vectors = self.embedding_model.embed_passages(texts=texts)

                    self.qdrant.add(
                        embedding_vecs=embedding_vectors,
                        texts=texts,
                        user=user_id,
                        doc=doc,
                        chat_id=chat_id,
                        chunks=chunks,
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
                chat_id=chat_id,
                chunks=chunks,
            )

    def query_stream(self, user_id: str, user_query: str, chat_id: str) -> Iterator[str]:
        chat_history = self.sql.select_chat_history(
            chat_id=chat_id,
            user_id=user_id
        )
        if not chat_history:
            self.sql.init_chat_history(chat_id=chat_id, user_id=user_id)
            chat_history = {
                "conversation": [],
                "summary": ""
            }

        current_summary = chat_history["summary"] or ""

        query_embedding = self.embedding_model.embed_query(user_query)
        query_retrieval = self.qdrant.search(
            user_id=user_id,
            query_text=user_query,
            query_embedding=query_embedding,
            chat_id=chat_id
        )
        answer_parts = []
        for token in self.chatbot.stream(
            user_prompt=user_query, 
            data=query_retrieval, 
            memory=current_summary
        ): 
            answer_parts.append(token)
            yield token

        answer = "".join(answer_parts)
        new_summary = self.chatbot.summarize_conversation(
            current_summary=current_summary,
            user_message=user_query,
            chatbot_message=answer
        )

        self.sql.update_chat_history(
            user_id=user_id,
            chat_id=chat_id,
            user_message=user_query,
            chatbot_message=answer,
            chat_summary=new_summary
        )

    def agent_query_stream(
        self,
        user_id: str,
        user_query: str,
        chat_id: str,
    ) -> Iterator[str]:
        users = self.sql.select_user(user_id)
        user_plan = (users[0].get("plan") or "Free") if users else "Free"
        if user_plan.strip().lower() != "pro":
            raise PermissionError("Only Pro users can use Agent mode.")

        chat_history = self.sql.select_chat_history(
            chat_id=chat_id,
            user_id=user_id
        )
        if not chat_history:
            self.sql.init_chat_history(chat_id=chat_id, user_id=user_id)
            chat_history = {
                "conversation": [],
                "summary": ""
            }

        current_summary = chat_history["summary"] or ""

        answer_parts = []
        for token in self.agent.stream(
            user_prompt=user_query,
            memory=current_summary,
            user_id=user_id,
            chat_id=chat_id,
        ):
            answer_parts.append(token)
            yield token

        answer = "".join(answer_parts)
        new_summary = self.agent.summarize_conversation(
            current_summary=current_summary,
            user_message=user_query,
            chatbot_message=answer
        )

        self.sql.update_chat_history(
            user_id=user_id,
            chat_id=chat_id,
            user_message=user_query,
            chatbot_message=answer,
            chat_summary=new_summary
        )

    def _source_summary(self, user_id: str, chat_id: str) -> str:
        """Initialize a chat and return its current conversation summary."""
        history = self.sql.select_chat_history(user_id=user_id, chat_id=chat_id)
        if not history:
            self.sql.init_chat_history(user_id=user_id, chat_id=chat_id)
        return (history or {}).get("summary") or ""

    def _document_names(self, user_id: str, chat_id: str) -> dict[str, str]:
        """Resolve legacy filenames exclusively inside the user's current chat."""
        return {
            row["document_id"]: row.get("file_name") or ""
            for row in self.sql.select_document_by_chat(user_id, chat_id)
        }

    def _finish_source_turn(self, user_id: str, chat_id: str, user_query: str,
                            answer: str, summary: str, turn_id: str,
                            registry: SourceRegistry, responder) -> PipelineEvent:
        """Persist snapshots before announcing a completed, saved answer."""
        sources = registry.snapshot()
        citations = validate_citations(answer, sources)
        new_summary = responder.summarize_conversation(
            current_summary=summary, user_message=user_query, chatbot_message=answer,
        )
        self.sql.update_chat_history(
            user_id=user_id, chat_id=chat_id, user_message=user_query,
            chatbot_message=answer, chat_summary=new_summary,
            source_metadata={
                "turn_id": turn_id, "sources": sources,
                **citations, "source_schema_version": 1,
            },
        )
        return PipelineEvent(event="citations", payload={
            "turn_id": turn_id, **citations, "saved": True,
        })

    def query_events(self, user_id: str, user_query: str, chat_id: str,
                     include_trace: bool = False) -> Iterator[PipelineEvent]:
        """Stream document evidence, answer tokens and persisted citation metadata."""
        summary = self._source_summary(user_id, chat_id)
        turn_id = str(uuid.uuid4())
        started = perf_counter()
        embedding = self.embedding_model.embed_query(user_query)
        embedding_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        hits = self.qdrant.search_hits(
            user_id=user_id, query_text=user_query, query_embedding=embedding,
            chat_id=chat_id,
        )
        retrieval_ms = (perf_counter() - started) * 1000
        if any(not hit.file_name for hit in hits):
            names = self._document_names(user_id, chat_id)
            hits = [hit.model_copy(update={"file_name": hit.file_name or names.get(hit.document_id, "")}) for hit in hits]
        registry = SourceRegistry()
        sources = registry.register(hits)
        yield PipelineEvent(event="sources", payload={
            "turn_id": turn_id, "sources": registry.snapshot(),
        })
        if include_trace:
            yield PipelineEvent(event="retrieval_trace", payload={
                "turn_id": turn_id, "score_type": "rrf", "limit": 10,
                "prefetch_limit": 20, "hnsw_ef": 128,
                "embedding_ms": embedding_ms, "retrieval_ms": retrieval_ms,
                "hits": [hit.model_dump(exclude={"content"}) for hit in hits],
                "context_point_ids": [source.qdrant_point_id for source in sources],
            })
        parts = []
        for token in self.chatbot.stream(
            user_prompt=user_query,
            data=CITATION_INSTRUCTIONS + "\n" + format_retrieval_context(sources),
            memory=summary,
        ):
            parts.append(token)
            yield PipelineEvent(event="token", payload={"content": token})
        yield self._finish_source_turn(
            user_id, chat_id, user_query, "".join(parts), summary,
            turn_id, registry, self.chatbot,
        )

    def agent_query_events(self, user_id: str, user_query: str,
                           chat_id: str) -> Iterator[PipelineEvent]:
        """Use a request-local registry for sources gathered by document tools."""
        users = self.sql.select_user(user_id)
        plan = (users[0].get("plan") or "Free") if users else "Free"
        if plan.strip().lower() != "pro":
            raise PermissionError("Only Pro users can use Agent mode.")
        summary = self._source_summary(user_id, chat_id)
        turn_id = str(uuid.uuid4())
        registry = SourceRegistry()
        parts = []
        yield PipelineEvent(event="sources", payload={"turn_id": turn_id, "sources": []})
        for event in self.agent.stream_events(
            user_prompt=user_query, memory=summary, user_id=user_id,
            chat_id=chat_id, registry=registry,
            document_names=self._document_names(user_id, chat_id),
        ):
            if event.event == "token":
                parts.append(event.payload["content"])
            yield event.model_copy(update={"payload": {**event.payload, "turn_id": turn_id}})
        yield self._finish_source_turn(
            user_id, chat_id, user_query, "".join(parts), summary,
            turn_id, registry, self.agent,
        )
