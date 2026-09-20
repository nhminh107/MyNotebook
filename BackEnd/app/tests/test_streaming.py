from langchain_core.messages import AIMessageChunk
from langchain_core.prompts import PromptTemplate

from BackEnd.app.chatbot.chatbot import Chatbot
from BackEnd.app.pipeline import Pipeline


class StubMemory:
    def __init__(self) -> None:
        self.saved_context = None

    def load_memory_variables(self, inputs: dict) -> dict[str, str]:
        return {"chat_history": "Previous summary"}

    def save_context(self, inputs: dict, outputs: dict) -> None:
        self.saved_context = (inputs, outputs)


class StubLlm:
    def __init__(self) -> None:
        self.prompt = None

    def stream(self, prompt):
        self.prompt = prompt
        yield AIMessageChunk(content="Hello")
        yield AIMessageChunk(content=" **world**")
        yield AIMessageChunk(content="")


def test_chatbot_stream_yields_chunks_and_saves_memory() -> None:
    chatbot = Chatbot.__new__(Chatbot)
    chatbot._memory = StubMemory()
    chatbot._llm = StubLlm()
    chatbot._prompt_template = PromptTemplate(
        template=(
            "History: {chat_history}\n"
            "Question: {user_prompt}\n"
            "Context: {info}"
        ),
        input_variables=["chat_history", "user_prompt", "info"],
    )

    chunks = list(chatbot.stream(user_prompt="Question", data="Context"))

    assert chunks == ["Hello", " **world**"]
    assert "Previous summary" in chatbot._llm.prompt.to_string()
    assert chatbot._memory.saved_context == (
        {"user_prompt": "Question"},
        {"text": "Hello **world**"},
    )


class StubEmbeddingModel:
    def embed_query(self, text: str) -> list[float]:
        assert text == "Question"
        return [0.1, 0.2]


class StubQdrant:
    def search(self, user_id: str, query_embedding: list[float]) -> str:
        assert user_id == "user-001"
        assert query_embedding == [0.1, 0.2]
        return "Retrieved context"


class StubChatbot:
    def stream(self, user_prompt: str, data: str):
        assert user_prompt == "Question"
        assert data == "Retrieved context"
        yield "First"
        yield " second"


def test_pipeline_query_stream_connects_retrieval_to_chatbot() -> None:
    pipeline = Pipeline(
        sql=None,
        qdrant=StubQdrant(),
        embedding_model=StubEmbeddingModel(),
        chatbot=StubChatbot(),
    )

    chunks = list(
        pipeline.query_stream(
            user_id="user-001",
            user_query="Question",
        )
    )

    assert chunks == ["First", " second"]
