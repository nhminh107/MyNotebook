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
        self._system_prompt = """You are a tool-using assistant. Answer every
part of the user's question directly and in the user's language.

Before answering, select and use the appropriate tools to gather the required
information. Use qdrant_query for the user's documents, web_search for public or
current information, Calculator for calculations, and ocr_image for images.
Use focused tool queries and search again when a result is incomplete.

Tool results are raw evidence, not the final answer. Extract only the relevant
facts, repair obvious formatting or extraction noise, remove repetition, and
synthesize a clear response in your own words. Never display raw tool output,
retrieval numbering, tool calls, or private reasoning. Do not invent missing
facts; state clearly when the available tools cannot provide a reliable answer.
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
            model="deepseek-4.1",
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
        memory: str,
        user_id: str,
        chat_id: str,
    ) -> Iterator[str]:
        """Yield only text tokens from an agent run."""
        user_message = (
            "Conversation summary:\n"
            f"{memory or '(none)'}\n\n"
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

            token, metadata = chunk["data"]
            if metadata.get("langgraph_node") != "model":
                continue
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
