from pydantic import BaseModel

class User: 
    user_id: str
    user_name: str
    user_pass: str

class Document: 
    document_id: str 
    user_id: str 
    type: str