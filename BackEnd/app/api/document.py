from collections.abc import Iterator
from functools import lru_cache
import json
import logging
import os
import secrets
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from BackEnd.app.chatbot.chatbot import Chatbot
from BackEnd.app.database.qdrant_manager import QDrant
from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.pipeline import Pipeline
from BackEnd.app.text_input.Embedding import EmbeddingModel
from BackEnd.app.chatbot.tools import ToolList
from BackEnd.app.chatbot.agents import Agents

from BackEnd.app.service.session_service import require_document_identity
from BackEnd.app.service.r2_storage import (
    CloudflareR2, DOCUMENT_CONTENT_TYPES, MAX_DOCUMENT_BYTES, READ_SIZE, StorageError,
    iter_document_bytes,
)

logger = logging.getLogger(__name__)


class RetrievalRequest(BaseModel):
    user_id: str = Field(min_length=1)
    chat_id: str = Field(min_length=1)
    user_query: str = Field(min_length=1)
    include_sources: bool = False
    include_trace: bool = False


def format_sse_event(event: str, payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def stream_retrieval_events(
    pipeline: Pipeline,
    user_id: str,
    user_query: str,
    chat_id: str,
    use_agent: bool = False,
    include_sources: bool = False,
    include_trace: bool = False,
) -> Iterator[str]:
    if include_sources:
        try:
            if use_agent:
                events = pipeline.agent_query_events(user_id, user_query, chat_id)
            else:
                events = pipeline.query_events(user_id, user_query, chat_id, include_trace=include_trace)
            for item in events:
                yield format_sse_event(item.event, item.payload)
        except Exception:
            logger.exception("Citation response stream failed (agent_mode=%s).", use_agent)
            yield format_sse_event("error", {"detail": "Unable to complete or save the answer. This turn was not confirmed as saved."})
            return
        yield format_sse_event("done", {"saved": True})
        return
    try:
        stream_method = (
            pipeline.agent_query_stream if use_agent else pipeline.query_stream
        )
        for token in stream_method(
            user_id=user_id,
            user_query=user_query,
            chat_id=chat_id
        ):
            yield format_sse_event("token", {"content": token})
    except Exception:
        logger.exception(
            "Document response stream failed (agent_mode=%s).",
            use_agent,
        )
        yield format_sse_event(
            "error",
            {"detail": "Unable to stream document information."},
        )
        return

    yield format_sse_event("done", {})


@lru_cache(maxsize=1)
def get_database() -> Supabase_Manager:
    return Supabase_Manager()


@lru_cache(maxsize=1)
def get_storage() -> CloudflareR2:
    return CloudflareR2()


@lru_cache(maxsize=1)
def get_pipeline() -> Pipeline:
    qdrant = QDrant()
    embedding_model = EmbeddingModel()
    chatbot = Chatbot()
    agent_tools = ToolList(
        llm=chatbot._llm,
        qdrant=qdrant,
        embedding_model=embedding_model,
    )
    return Pipeline(
        sql=get_database(),
        qdrant=qdrant,
        embedding_model=embedding_model,
        chatbot=chatbot,
        agent=Agents(agent_tools),
        storage=get_storage(),
    )


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
    dependencies=[Depends(require_document_identity)],
)


@router.get("/files/{document_id}")
def get_document_file(document_id: str, request: Request) -> StreamingResponse:
    """Stream an original file only to its authenticated document owner."""
    try:
        row = get_database().select_document_for_user(
            document_id, request.state.user_id,
        )
        if not row or not row.get("storage_key"):
            raise HTTPException(status_code=404, detail="Original document not found.")
        storage = get_storage()
        if row.get("storage_bucket") != storage.bucket:
            raise HTTPException(status_code=404, detail="Original document not found.")
        content_type = DOCUMENT_CONTENT_TYPES.get(row.get("type"))
        if content_type is None:
            raise HTTPException(status_code=415, detail="Unsupported document type.")
        body = storage.open_document(row["storage_key"])
        filename = Path(row.get("file_name") or "document").name
        disposition = "attachment" if row["type"] == ".docx" else "inline"
        return StreamingResponse(
            iter_document_bytes(body), media_type=content_type,
            headers={
                "Content-Disposition": (
                    f"{disposition}; filename*=UTF-8''{quote(filename, safe='')}"
                ),
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
            background=BackgroundTask(body.close),
        )
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Original document not found.") from exc
    except StorageError as exc:
        logger.exception("Original document storage is unavailable.")
        raise HTTPException(
            status_code=502, detail="Original document storage is unavailable.",
        ) from exc
    except Exception as exc:
        logger.exception("Unable to load the original document.")
        raise HTTPException(
            status_code=500, detail="Unable to load the original document.",
        ) from exc


@router.get("/chats/{user_id}")
def get_chat_histories(user_id: str):
    user_id = user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID must not be blank.")

    try:
        chats = get_database().select_chat_histories_by_user(user_id)
        return {"data": chats}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to load chat history.",
        ) from exc


@router.get("/chats/{user_id}/{chat_id}")
def get_chat_history(user_id: str, chat_id: str):
    user_id = user_id.strip()
    chat_id = chat_id.strip()
    if not user_id or not chat_id:
        raise HTTPException(
            status_code=400,
            detail="User ID and chat ID must not be blank.",
        )

    try:
        database = get_database()
        chat = database.select_chat_history(user_id=user_id, chat_id=chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat history not found.")

        documents = database.select_document_by_chat(
            user_id=user_id,
            chat_id=chat_id,
        )
        return {
            "data": {
                "chat": chat,
                "documents": documents,
            }
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to load chat history.",
        ) from exc


@router.post("/upload")
async def upload_document(
    user_id: str = Form(...),
    chat_id: str = Form(...),
    file: UploadFile = File(...),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="File name is required",
        )
    extension = Path(file.filename).suffix.lower()
    allowed_extension = {
        ".pdf",
        ".docx",
        ".txt",
    }
    if extension not in allowed_extension:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {extension}",
        )
    try:
        with NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as temp_file:
            temp_path = temp_file.name

            size = 0
            while content := await file.read(READ_SIZE):
                size += len(content)
                if size > MAX_DOCUMENT_BYTES:
                    raise HTTPException(
                        status_code=413, detail="Document exceeds the 300 MB upload limit.",
                    )
                temp_file.write(content)
            if size == 0:
                raise HTTPException(status_code=400, detail="Document must not be empty.")

        pipeline = await run_in_threadpool(get_pipeline)
        doc = await run_in_threadpool(
            pipeline.insert_doc_pipeline,
            doc_path=temp_path,
            user_id=user_id,
            chat_id=chat_id,
            file_name=file.filename
        )

        return {
            "message": "Document uploaded successfully.",
            "filename": file.filename,
            "user_id": user_id,
            "chat_id": chat_id,
            "document_id": doc.document_id if doc is not None else None,
            "document_url": doc.document_url if doc is not None else None,
        }

    except HTTPException:
        raise
    except StorageError as exc:
        logger.exception("Original document upload to R2 failed.")
        raise HTTPException(
            status_code=502, detail="Unable to store the original document in Cloudflare R2.",
        ) from exc
    except Exception as exc:
        logger.exception("Document upload failed.")
        raise HTTPException(
            status_code=500,
            detail="Unable to upload the document. Check backend configuration and the source metadata/document storage migrations.",
        ) from exc

    finally:
        if "temp_path" in locals():
            Path(temp_path).unlink(missing_ok=True)


@router.post("/retrieval/agent-stream")
def stream_agent_retrieve(
    request: RetrievalRequest,
    trace_key: str | None = Header(default=None, alias="X-Retrieval-Trace-Key"),
) -> StreamingResponse:

    if request.include_trace:
        raise HTTPException(status_code=400, detail="Detailed retrieval trace is supported only by standard retrieval.")
    user_id = request.user_id.strip()
    user_query = request.user_query.strip()
    chat_id = request.chat_id.strip()

    if not user_id or not chat_id or not user_query:
        raise HTTPException(
            status_code=400,
            detail="User ID, chat ID and query must not be blank"
        )

    try:
        pipeline = get_pipeline()
    except Exception as exc:
        logger.exception("Unable to initialize the document pipeline.")
        raise HTTPException(
            status_code=500,
            detail="Unable to initialize document retrieval.",
        ) from exc

    return StreamingResponse(
        stream_retrieval_events(
            pipeline=pipeline,
            user_id=user_id,
            user_query=user_query,
            chat_id=chat_id,
            use_agent=True,
            include_sources=request.include_sources,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/retrieval/stream")
def stream_retrieve_document(
    request: RetrievalRequest,
    trace_key: str | None = Header(default=None, alias="X-Retrieval-Trace-Key"),
) -> StreamingResponse:
    if request.include_trace:
        expected = os.environ.get("NOTEBOOK_RETRIEVAL_TRACE_KEY")
        if not expected or not isinstance(trace_key, str) or not secrets.compare_digest(trace_key, expected):
            raise HTTPException(status_code=403, detail="Retrieval trace is not available to this client.")
        if not request.include_sources:
            raise HTTPException(status_code=400, detail="Trace requires include_sources.")
    user_id = request.user_id.strip()
    user_query = request.user_query.strip()
    chat_id = request.chat_id.strip()
    if not user_id or not chat_id or not user_query:
        raise HTTPException(
            status_code=400,
            detail="User ID, chat ID and query must not be blank.",
        )

    try:
        pipeline = get_pipeline()
    except Exception as exc:
        logger.exception("Unable to initialize the document pipeline.")
        raise HTTPException(
            status_code=500,
            detail="Unable to initialize document retrieval.",
        ) from exc

    return StreamingResponse(
        stream_retrieval_events(
            pipeline=pipeline,
            user_id=user_id,
            user_query=user_query,
            chat_id=chat_id,
            include_sources=request.include_sources,
            include_trace=request.include_trace,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
