from pydantic import BaseModel

class User(BaseModel): 
    user_id: str
    user_name: str
    user_pass: str

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

class Register(BaseModel):
    user_name:str
    password: str

class Login(BaseModel):
    user_name:str
    password:str
