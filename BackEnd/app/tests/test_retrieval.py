import time

from BackEnd.app.chatbot.chatbot import Chatbot
from BackEnd.app.database.qdrant_manager import QDrant
from BackEnd.app.database.sql_manager import Supabase_Manager
from BackEnd.app.pipeline import Pipeline
from BackEnd.app.text_input.Embedding import EmbeddingModel


TEST_USER_ID = "001"
TEST_CHAT_ID = "chat-001"
TEST_QUERIES = [
    "What is tokenization and why is it important for large language models?",
    "How does retrieval-augmented generation improve large language model responses?",
    "What is the difference between encoder-only and decoder-only Transformer models?",
]


if __name__ == "__main__":
    pipeline = Pipeline(
        sql=Supabase_Manager(),
        qdrant=QDrant(),
        embedding_model=EmbeddingModel(),
        chatbot=Chatbot(),
    )

    elapsed_times = []

    for prompt in TEST_QUERIES:
        started_at = time.perf_counter()
        result = "".join(
            pipeline.query_stream(
                user_id=TEST_USER_ID,
                user_query=prompt,
                chat_id=TEST_CHAT_ID,
            )
        )
        elapsed_times.append(time.perf_counter() - started_at)

        print(f"\nPrompt: {prompt}")
        print(f"Result: {result}")

    average_time = sum(elapsed_times) / len(elapsed_times)
    print(f"\nAverage time: {average_time:.2f} seconds")
