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

    def init_chat_history(self, chat_id: str, user_id: str):
        data = {
            "chat_id": chat_id,
            "user_id": user_id,
            "conversation": [
                {
                    "user": "Hi",
                    "chatbot": "Good mornig! How can I help you ?"
                }
            ]
        }

        response = (
            self.supabase.table("chat_history").insert(data).execute()
        )
        return response.data

    def update_chat_history(self, chat_id: str, user_message: str, chatbot_message: str, chat_summary: str):
        response = (
            self.supabase.table("chat_history")
            .select("conversation")
            .eq("chat_id", chat_id)
            .single()
            .execute()
        )

        conversation = response.data["conversation"] or []
        conversation.append({
            "user": user_message,
            "chatbot": chatbot_message
        })

        data = {
            "conversation": conversation,
            "summary": chat_summary
        }


        try:
            response = (
                self.supabase.table("chat_history").update(data).eq("chat_id", chat_id).execute()
            )
            return 200
        except Exception as e:
            raise e

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
        respone = (self.supabase.table("chat_history").
                   select("*").
                   eq("user_id", user_id).
                   eq("chaT_id", chat_id).
                   execute()
                   )
        return respone.data
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
