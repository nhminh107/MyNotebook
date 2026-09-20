from fastapi import FastAPI

from BackEnd.app.api.document import router as document_router
from BackEnd.app.api.auth import router as auth_router


app = FastAPI(
    title="MyNoteBook API",
    version="1.0.0",
)


app.include_router(auth_router)
app.include_router(document_router)


@app.get("/")
def root():
    return {
        "message": "MyNoteBook API is running"
    }