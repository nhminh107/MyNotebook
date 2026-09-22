import os
from supabase import create_client, Client
from postgrest import APIError
from dotenv import load_dotenv
from BackEnd.app.database.sql_models import User, Document, Chunk
from BackEnd.app.text_sanitizer import sanitize_text
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
            "user_name": user.user_name,
            "plan": user.plan
        }

        response = (
            self.supabase.table("user").insert(data).execute()
        )
        return response.data

    def insert_document(self, doc: Document): 
        data = {
            "document_id": doc.document_id, 
            "user_id": doc.user_id, 
            "type": doc.type,
            "chat_id": doc.chat_id,
            "file_name": doc.file_name
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
                "content": sanitize_text(chunk.content),
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

    def init_chat_history(self, chat_id: str, user_id: str):
        data = {
            "chat_id": chat_id,
            "user_id": user_id,
            "conversation": [],
            "summary": ""
        }

        response = (
            self.supabase.table("chat_history").insert(data).execute()
        )
        return response.data

    def update_chat_history(self, user_id: str, chat_id: str, user_message: str, chatbot_message: str, chat_summary: str):
        response = (
            self.supabase.table("chat_history")
            .select("conversation")
            .eq("user_id", user_id)
            .eq("chat_id", chat_id)
            .single()
            .execute()
        )

        conversation = response.data["conversation"] or []
        conversation.append({
            "user": sanitize_text(user_message),
            "chatbot": sanitize_text(chatbot_message)
        })

        data = {
            "conversation": conversation,
            "summary": sanitize_text(chat_summary)
        }


        response = (
            self.supabase.table("chat_history")
            .update(data)
            .eq("user_id", user_id)
            .eq("chat_id", chat_id)
            .execute()
        )
        return response.data

    def delete_document(self, doc_id: str):
        chunks_response = (
            self.supabase.table("chunks")
            .delete()
            .eq("document_id", doc_id)
            .execute()
        )

        document_response = (
            self.supabase.table("document")
            .delete()
            .eq("document_id", doc_id)
            .execute()
        )

        return {
            "document": document_response.data,
            "chunks": chunks_response.data
        }

    def select_user(self, user_id: str):
        response =(self.supabase.table("user").select("*").eq("user_id",user_id).execute())
        return response.data

    def select_chat_history(self, user_id: str, chat_id: str):
        response = (
            self.supabase.table("chat_history")
            .select("*")
            .eq("user_id", user_id)
            .eq("chat_id", chat_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def select_chat_histories_by_user(self, user_id: str):
        response = (
            self.supabase.table("chat_history")
            .select("chat_id, created_at, conversation")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data

    def select_document(self, document_id:str):
        response=(self.supabase.table("document").select("*").eq("document_id", document_id).execute())
        return response.data

    def select_document_by_user(self, user_id:str):
        response= (self.supabase.table("document").select("*").eq("user_id", user_id).execute())
        return response.data

    def select_document_by_chat(self, user_id: str, chat_id: str):
        response = (
            self.supabase.table("document")
            .select("*")
            .eq("user_id", user_id)
            .eq("chat_id", chat_id)
            .execute()
        )
        return response.data

    def select_chunk_by_document(self, document_id:str):
        response=(self.supabase.table("chunks").select("*").eq("document_id",document_id).execute())
        return response.data

    def select_user_by_name(self, user_name:str):
        response=(self.supabase.table("user").select("*").eq("user_name", user_name).execute())
        return response.data
