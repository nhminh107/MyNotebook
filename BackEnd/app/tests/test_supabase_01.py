from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.database.sql_models import User, Document, Chunk

user = User(user_id = "001", user_name = "test", user_pass = "12421ddqdwd2")
doc = Document(document_id = "001", user_id = "001", type="pdf")
chunk = Chunk(chunk_id="001", document_id="001", content="Test")

mng = Supabase_Manager()
mng.insert_user(user)
mng.insert_document(doc)
mng.insert_chunks(chunk)