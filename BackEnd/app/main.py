from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from BackEnd.app.api.auth import router as auth_router
from BackEnd.app.api.document import router as document_router


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "FrontEnd"


app = FastAPI(
    title="MyNoteBook API",
    version="1.0.0",
)


app.include_router(auth_router)
app.include_router(document_router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    return {
        "message": "MyNoteBook API is running",
    }
