import time

from BackEnd.app.database.qdrant_manager import QDrant
from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.pipeline import Pipeline
from BackEnd.app.text_input.Embedding import EmbeddingModel


TEST_DOCUMENT_PATH = "/home/nhminh/Downloads/Hands-On-Large-Language-Models.pdf"
TEST_USER_ID = "001"


def test_insert_doc_pipeline() -> None:
    started_at = time.perf_counter()
    status = "FAILED"

    try:
        pipeline = Pipeline(
            sql=Supabase_Manager(),
            qdrant=QDrant(),
            embedding_model=EmbeddingModel(),
        )

        pipeline.insert_doc_pipeline(
            doc_path=TEST_DOCUMENT_PATH,
            user_id=TEST_USER_ID,
        )
        status = "SUCCESS"
    finally:
        elapsed_seconds = time.perf_counter() - started_at
        print(f"\nStatus: {status}")
        print(f"Processing time: {elapsed_seconds:.2f} seconds")
