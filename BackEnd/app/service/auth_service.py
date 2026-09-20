from uuid import uuid4
import bcrypt
from jose import jwt 
from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.database.sql_models import (User, Register, Login,)

class AuthService:
    def __init__(self, database:Supabase_Manager | None=None):
        self.database=database or Supabase_Manager()

    def register(self, request:Register):
        existing_user=self.database.select_user_by_name(request.user_name)

        if existing_user:
            raise ValueError("User name already exists.")

        hash_password=bcrypt.hashpw(request.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user=User(
            user_id=str(uuid4()), user_name=request.user_name, user_pass=hash_password,
        )
        self.database.insert_user(user)

        return {
            "user_id":user.user_id,
            "user_name": user.user_name,
        }

    def login(self, request:Login):
        users=self.database.select_user_by_name(
            request.user_name
        )

        if not users:
            raise ValueError("Invalid username or password")

        user=users[0]

        password_valid=bcrypt.checkpw(
            request.password.encode("utf-8"),
            user["user_password"].encode("utf-8"),
        )

        if not password_valid:
            raise ValueError("Invalid username or password")

        return {
            "user_id": user["user_id"],
            "user_name": user["user_name"],
        }
