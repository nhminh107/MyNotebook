import sqlite3
from BackEnd.app.database.sql_models import User, Document
class SQL_Manager(): 
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)

    def table_user(self): 
        """Temporal table, I'll update this table in version 1"""
        query = """
            CREATE TABLE user (
                user_id TEXT PRIMARY KEY, 
                user_password TEXT,
                user_name TEXT
            ); 
        """
        self.conn.execute(query)

    def create_user(self, user: User):
        query = """
            INSERT INTO user values (?, ?, ?)
        """
        cursor = self.conn.cursor()
        try: 
            cursor.execute(query, (user.user_id, user.user_pass, user.user_pass))
            self.conn.commit()
            return 200
        except Exception as e: 
            self.conn.rollback()
            return 500 

    def table_document(self): 
        query = """
            CREATE TABLE document (
                document_id TEXT PRIMARY KEY, 
                user_id TEXT NOT NULL, 
                type TEXT

                CONSTRAINT Fk_user FOREIGN KEY (document_id) REFERENCESS user(user_id)
            )
        """
        self.conn.execute(query)

    def create_document(self, doc: Document): 
        query = """
                INSERT INTO document values (?, ?, ?)
                """
        cursor = self.conn.cursor()
        try: 
            cursor.execute(query, (doc.document_id, doc.user_id, doc.type))
            self.conn.commit()
            return 200 

        except Exception as e: 
            self.conn.rollback()
            return 500 


    
