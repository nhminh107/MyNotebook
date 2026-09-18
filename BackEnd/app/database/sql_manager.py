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

    def insert_chunks(self, chunk: Chunk):
        data = {
            "chunk_id": chunk.chunk_id, 
            "document_id": chunk.document_id, 
            "content": chunk.content
        }

        response = (
            self.supabase.table("chunks").insert(data).execute()
        )
        return response.data