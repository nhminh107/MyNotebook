from urllib.parse import quote

from pydantic import BaseModel, Field

class User(BaseModel): 
    user_id: str
    user_name: str
    user_pass: str
    plan: str = "Free"

class Document(BaseModel): 
    document_id: str 
    user_id: str 
    type: str
    chat_id: str
    file_name: str = ""
    storage_bucket: str | None = None
    storage_key: str | None = None
    content_type: str | None = None
    file_size: int | None = Field(default=None, gt=0)
    sha256: str | None = None
    etag: str | None = None

    @property
    def document_url(self) -> str | None:
        """Return a stable authenticated route rather than a public bucket URL."""
        if not self.storage_key or not self.storage_bucket:
            return None
        return f"/documents/files/{quote(self.document_id, safe='')}"

class Chunk(BaseModel): 
    chunk_id: str 
    document_id: str 
    content: str
    page: int | None = Field(default=None, ge=1)
    chunk_index: int | None = Field(default=None, ge=0)
    ocr_used: bool | None = None

class Register(BaseModel):
    user_name:str
    password: str

class Login(BaseModel):
    user_name:str
    password:str
