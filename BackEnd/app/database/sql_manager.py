import os
from supabase import create_client, Client
from postgrest import APIError
from dotenv import load_dotenv
from BackEnd.app.database.sql_models import User, Document, Chunk
load_dotenv()


class Supabase_Manager():
    def __init__(self):
        self.supabase: Client = create_client(
            os.environ.get("SUPABASE_URL"),
            os.environ.get("SUPABASE_PUBLISHABLE_KEY")
        )

    def insert_user(self, user: User): 
        data = {
            "user_id": user.user_id, 
            "user_password": user.user_pass, 
            "user_name": user.user_name
        }

        response = (
            self.supabase.table("user").insert(data).execute()
        )
        return response.data

    def insert_document(self, doc: Document): 
        data = {
            "document_id": doc.document_id, 
            "user_id": doc.user_id, 
            "type": doc.type
        }
        response = (
            self.supabase.table("document").insert(data).execute()
        )
        return response.data

    def insert_chunks(self, chunks: list[Chunk]):
        if not chunks:
            return []

        data = [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "content": chunk.content,
            }
            for chunk in chunks
        ]

        response = (
            self.supabase
            .table("chunks")
            .insert(data)
            .execute()
        )

        return response.data

    def select_user(self, user_id: str):
        response =(self.supabase.table("user").select("*").eq("user_id",user_id).execute())
        return response.data

    def select_document(self, document_id:str):
        response=(self.supabase.table("document").select("*").eq("document_id", document_id).execute())
        return response.data

    def select_document_by_user(self, user_id:str):
        response= (self.supabase.table("document").select("*").eq("user_id", user_id).execute())
        return response.data

    def select_chunk_by_document(self, document_id:str):
        response=(self.supabase.table("chunks").select("*").eq("document_id",document_id).execute())
        return response.data

    def select_user_by_name(self, user_name:str):
        response=(self.supabase.table("user").select("*").eq("user_name", user_name).execute())
        return response.data
    