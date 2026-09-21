from collections.abc import Iterator
from functools import lru_cache
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from BackEnd.app.chatbot.chatbot import Chatbot
from BackEnd.app.database.qdrant_manager import QDrant
from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.pipeline import Pipeline
from BackEnd.app.text_input.Embedding import EmbeddingModel


class RetrievalRequest(BaseModel):
    user_id: str = Field(min_length=1)
    chat_history: str = Field(min_length=1)
    user_query: str = Field(min_length=1)


class RetrievalResponse(BaseModel):
    message: str
    data: str


def format_sse_event(event: str, payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def stream_retrieval_events(
    pipeline: Pipeline,
    user_id: str,
    user_query: str,
) -> Iterator[str]:
    try:
        for token in pipeline.query_stream(
            user_id=user_id,
            user_query=user_query,
        ):
            yield format_sse_event("token", {"content": token})
    except Exception:
        yield format_sse_event(
            "error",
            {"detail": "Unable to stream document information."},
        )
        return

    yield format_sse_event("done", {})


@lru_cache(maxsize=5)
def get_pipeline() -> Pipeline:
    return Pipeline(
        sql=Supabase_Manager(),
        qdrant=QDrant(),
        embedding_model=EmbeddingModel(),
        chatbot=Chatbot(),
    )


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


@router.post("/upload")
async def upload_document(
    user_id: str = Form(...),
    file: UploadFile = File(...),
):
    pipeline = get_pipeline()

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

            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        pipeline.insert_doc_pipeline(
            doc_path=temp_path,
            user_id=user_id,
        )

        return {
            "message": "Document uploaded successfully.",
            "filename": file.filename,
            "user_id": user_id,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:
        if "temp_path" in locals():
            Path(temp_path).unlink(missing_ok=True)


@router.post("/retrieval", response_model=RetrievalResponse)
def retrieve_document(
    request: RetrievalRequest,
) -> RetrievalResponse:
    user_id = request.user_id.strip()
    user_query = request.user_query.strip()

    if not user_id or not user_query:
        raise HTTPException(
            status_code=400,
            detail="User ID and query must not be blank.",
        )

    try:
        pipeline = get_pipeline()
        result = pipeline.query(
            user_id=user_id,
            user_query=user_query,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve document information.",
        ) from exc

    return RetrievalResponse(
        message="Retrieval completed successfully.",
        data=result,
    )


@router.post("/retrieval/stream")
def stream_retrieve_document(
    request: RetrievalRequest,
) -> StreamingResponse:
    user_id = request.user_id.strip()
    user_query = request.user_query.strip()

    if not user_id or not user_query:
        raise HTTPException(
            status_code=400,
            detail="User ID and query must not be blank.",
        )

    try:
        pipeline = get_pipeline()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to initialize document retrieval.",
        ) from exc

    return StreamingResponse(
        stream_retrieval_events(
            pipeline=pipeline,
            user_id=user_id,
            user_query=user_query,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
