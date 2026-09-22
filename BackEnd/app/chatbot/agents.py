import os
from collections.abc import Iterator
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.agents.middleware import ToolCallLimitMiddleware

from BackEnd.app.chatbot.tools import ToolList
from BackEnd.app.text_sanitizer import sanitize_text

load_dotenv()


@dataclass
class AppContext:
    user_id: str
    chat_id: str


MINTROUTE_API = os.getenv("LLM_API_KEY")


class Agents:
    def __init__(self, agent_tools: ToolList):
        self._agent_tools = agent_tools
        self._system_prompt = """You are a helpful retrieval-augmented assistant.

Answer the user's question using the conversation and retrieval information in
the messages. Retrieval results are ordered from most relevant to least
relevant.

Follow these rules:
- Prefer the supplied retrieval information when it is relevant.
- If that information is missing or insufficient, use the available tools.
- Do not invent facts. Clearly state when reliable information is unavailable.
- Cite or identify the source when the tool result provides one.
- Format the final answer as clear Markdown when structure improves readability.
- Do not expose private reasoning or tool-call internals in the final answer.
"""
        self._summary_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You maintain a concise conversation summary for future
assistant turns. Update the current summary using the latest user and assistant
messages. Preserve important facts, user preferences, decisions, unresolved
questions, and references needed to understand follow-up messages. Do not
answer the user or add unsupported information. Return only the updated summary
in plain text.""",
                ),
                (
                    "human",
                    """Current summary:
{summary}

New lines of conversation:
{new_lines}""",
                ),
            ]
        )

        self._summary_llm = ChatOpenAI(
            model="nemotron-3-ultra-free",
            temperature=0.1,
            base_url="https://api.mintrouter.ai/v1",
            api_key=MINTROUTE_API,
        )
        self._llm = ChatOpenAI(
            model="deepseek-4.1",
            temperature=0.1,
            base_url="https://api.mintrouter.ai/v1",
            api_key=MINTROUTE_API,
            streaming=True
        )
        self._agent = create_agent(
            model=self._llm,
            tools=self._agent_tools.tools,
            system_prompt=self._system_prompt,
            context_schema=AppContext,
            middleware=[
                ToolCallLimitMiddleware(
                    run_limit=10
                )
            ]
        )
        self._summary_chain = (
            self._summary_prompt | self._summary_llm | StrOutputParser()
        )

    def stream(
        self,
        user_prompt: str,
        data: str,
        memory: str,
        user_id: str,
        chat_id: str,
    ) -> Iterator[str]:
        """Yield only text tokens from an agent run."""
        user_message = (
            "Conversation summary:\n"
            f"{memory or '(none)'}\n\n"
            "Retrieval information:\n"
            f"{data or '(none)'}\n\n"
            "Question:\n"
            f"{user_prompt}"
        )

        for chunk in self._agent.stream(
            {"messages": [{"role": "user", "content": user_message}]},
            context=AppContext(user_id=user_id, chat_id=chat_id),
            stream_mode="messages",
            version="v2",
        ):
            if chunk["type"] != "messages":
                continue

            token, _metadata = chunk["data"]
            text = sanitize_text(token.text)
            if text:
                yield text

    def summarize_conversation(
        self,
        current_summary: str,
        user_message: str,
        chatbot_message: str,
    ) -> str:
        """Return an updated summary containing the latest conversation turn."""
        new_lines = (
            f"User: {user_message}\n"
            f"Chatbot: {chatbot_message}"
        )
        result = self._summary_chain.invoke(
            {
                "summary": current_summary,
                "new_lines": new_lines,
            }
        )
        return sanitize_text(result).strip()
