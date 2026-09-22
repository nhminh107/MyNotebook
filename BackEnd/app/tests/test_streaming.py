from langchain_core.messages import AIMessageChunk
from langchain_core.prompts import PromptTemplate

from BackEnd.app.chatbot.agents import Agents, AppContext
from BackEnd.app.chatbot.chatbot import Chatbot
from BackEnd.app.pipeline import Pipeline


class StubLlm:
    def __init__(self) -> None:
        self.prompt = None

    def stream(self, prompt):
        self.prompt = prompt
        yield AIMessageChunk(content="Hello")
        yield AIMessageChunk(content=" **world**")
        yield AIMessageChunk(content="\x00")
        yield AIMessageChunk(content="")


def test_chatbot_stream_uses_provided_summary() -> None:
    chatbot = Chatbot.__new__(Chatbot)
    chatbot._llm = StubLlm()
    chatbot._prompt_template = PromptTemplate(
        template=(
            "History: {chat_history}\n"
            "Question: {user_prompt}\n"
            "Context: {info}"
        ),
        input_variables=["chat_history", "user_prompt", "info"],
    )

    chunks = list(
        chatbot.stream(
            user_prompt="Question",
            data="Context",
            memory="Previous summary",
        )
    )

    assert chunks == ["Hello", " **world**"]
    assert "Previous summary" in chatbot._llm.prompt.to_string()


class StubToken:
    def __init__(self, text: str) -> None:
        self.text = text


class StubAgent:
    def __init__(self) -> None:
        self.input = None
        self.options = None

    def stream(self, input_data, **options):
        self.input = input_data
        self.options = options
        yield {
            "type": "messages",
            "data": (StubToken("Hello"), {"langgraph_node": "model"}),
        }
        yield {
            "type": "messages",
            "data": (StubToken(" world"), {"langgraph_node": "model"}),
        }
        yield {
            "type": "messages",
            "data": (StubToken("\x00"), {"langgraph_node": "model"}),
        }
        yield {
            "type": "messages",
            "data": (StubToken(""), {"langgraph_node": "model"}),
        }


def test_agent_stream_yields_text_and_passes_runtime_context() -> None:
    stub_agent = StubAgent()
    agents = Agents.__new__(Agents)
    agents._agent = stub_agent

    chunks = list(
        agents.stream(
            user_prompt="Question",
            memory="Previous summary",
            user_id="user-001",
            chat_id="chat-001",
        )
    )

    assert chunks == ["Hello", " world"]
    assert stub_agent.input == {
        "messages": [
            {
                "role": "user",
                "content": (
                    "Conversation summary:\n"
                    "Previous summary\n\n"
                    "Question:\n"
                    "Question"
                ),
            }
        ]
    }
    assert stub_agent.options == {
        "context": AppContext(user_id="user-001", chat_id="chat-001"),
        "stream_mode": "messages",
        "version": "v2",
    }


class StubSummaryChain:
    def __init__(self) -> None:
        self.payload = None

    def invoke(self, payload):
        self.payload = payload
        return " Updated summary "


def test_agent_summarize_conversation_updates_existing_summary() -> None:
    summary_chain = StubSummaryChain()
    agents = Agents.__new__(Agents)
    agents._summary_chain = summary_chain

    result = agents.summarize_conversation(
        current_summary="Previous summary",
        user_message="Question",
        chatbot_message="Answer",
    )

    assert result == "Updated summary"
    assert summary_chain.payload == {
        "summary": "Previous summary",
        "new_lines": "User: Question\nChatbot: Answer",
    }


class StubEmbeddingModel:
    def embed_query(self, text: str) -> list[float]:
        assert text == "Question"
        return [0.1, 0.2]


class StubQdrant:
    def search(
        self,
        user_id: str,
        query_text: str,
        query_embedding: list[float],
        chat_id: str,
    ) -> str:
        assert user_id == "user-001"
        assert query_text == "Question"
        assert query_embedding == [0.1, 0.2]
        assert chat_id == "chat-001"
        return "Retrieved context"


class StubChatbot:
    def stream(self, user_prompt: str, data: str, memory: str):
        assert user_prompt == "Question"
        assert data == "Retrieved context"
        assert memory == "Previous summary"
        yield "First"
        yield " second"

    def summarize_conversation(
        self,
        current_summary: str,
        user_message: str,
        chatbot_message: str,
    ) -> str:
        assert current_summary == "Previous summary"
        assert user_message == "Question"
        assert chatbot_message == "First second"
        return "Updated summary"


class StubSql:
    def __init__(self) -> None:
        self.updated = None

    def select_chat_history(self, user_id: str, chat_id: str) -> dict:
        assert user_id == "user-001"
        assert chat_id == "chat-001"
        return {"conversation": [], "summary": "Previous summary"}

    def update_chat_history(self, **data) -> None:
        self.updated = data


def test_pipeline_query_stream_connects_retrieval_to_chatbot() -> None:
    sql = StubSql()
    pipeline = Pipeline(
        sql=sql,
        qdrant=StubQdrant(),
        embedding_model=StubEmbeddingModel(),
        chatbot=StubChatbot(),
    )

    chunks = list(
        pipeline.query_stream(
            user_id="user-001",
            user_query="Question",
            chat_id="chat-001",
        )
    )

    assert chunks == ["First", " second"]
    assert sql.updated == {
        "user_id": "user-001",
        "chat_id": "chat-001",
        "user_message": "Question",
        "chatbot_message": "First second",
        "chat_summary": "Updated summary",
    }
