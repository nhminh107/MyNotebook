from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.database.qdrant_manager import QDrant
from BackEnd.app.text_input.Embedding import EmbeddingModel
from BackEnd.app.pipeline import Pipeline 

router=APIRouter(
    prefix="/documents",
    tags=["Documents"]
)

sql=Supabase_Manager()
qdrant=QDrant()
embedding=EmbeddingModel()

pipeline=Pipeline(
    sql=sql,
    qdrant=qdrant,
    embedding_model=embedding,
)

router.post("/upload")

async def upload_document(user_id: str=Form(...),
                          file:UploadFile=File(...),):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="File name is required"
        )
    extension=Path(file.filename).suffix.lower()
    allowed_extension={
        ".pdf",
        ".docx",
        ".txt",
    }
    if extension is not allowed_extension:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {extension}"
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
    
