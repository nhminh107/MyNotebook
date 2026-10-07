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
