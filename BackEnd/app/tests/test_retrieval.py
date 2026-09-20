import time

from BackEnd.app.chatbot.chatbot import Chatbot
from BackEnd.app.database.qdrant_manager import QDrant
from BackEnd.app.pipeline import Pipeline
from BackEnd.app.text_input.Embedding import EmbeddingModel


TEST_USER_ID = "001"
TEST_QUERIES = [
    "What is tokenization and why is it important for large language models?",
    "How does retrieval-augmented generation improve large language model responses?",
    "What is the difference between encoder-only and decoder-only Transformer models?",
]


if __name__ == "__main__":
    pipeline = Pipeline(
        sql=None,
        qdrant=QDrant(),
        embedding_model=EmbeddingModel(),
        chatbot=Chatbot(),
    )

    elapsed_times = []

    for prompt in TEST_QUERIES:
        started_at = time.perf_counter()
        result = pipeline.query(user_id=TEST_USER_ID, user_query=prompt)
        elapsed_times.append(time.perf_counter() - started_at)

        print(f"\nPrompt: {prompt}")
        print(f"Result: {result}")

    average_time = sum(elapsed_times) / len(elapsed_times)
    print(f"\nAverage time: {average_time:.2f} seconds")
