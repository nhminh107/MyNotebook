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

The user message contains a conversation summary and a question. Use the
qdrant_query tool whenever the question asks about the user's documents. Search
the public web only when document retrieval cannot answer a requested part or
when the user explicitly asks for external or current information.

Follow these rules:
- First identify every part of the user's question and answer each part.
- For multi-part requests, use focused tool queries for each distinct information
  need instead of combining unrelated topics into one broad retrieval query.
- If the first document search is incomplete or noisy, refine the query and
  search again before concluding that the information is unavailable.
- Treat passages returned by retrieval tools as evidence, not as a ready-made
  answer.
- Synthesize the relevant facts into a coherent response in your own words.
- Combine overlapping passages, remove repetition, and organize information in
  a logical order.
- Never dump the retrieval passages, reproduce their numbering, or copy long
  excerpts when a concise synthesis will answer the question.
- Retrieved text may contain broken spacing, misplaced page numbers, repeated
  headers, table-of-contents fragments, words split across lines, or passages
  returned out of document order. Infer the intended meaning from the available
  evidence, reconstruct readable sentences, and present the information with
  clean formatting. Never reproduce extraction artifacts in the final answer.
- Do not silently repair text when the intended meaning is ambiguous. State the
  uncertainty or retrieve more evidence instead.
- Clearly separate information supported by the user's documents from
  additional information obtained through tools.
- Do not invent facts. State clearly when reliable information is unavailable.
- Cite or identify a source when a tool result provides one.
- Respond in the same language as the user unless they request another language.
- Format the final answer as clear Markdown when structure improves readability.
- Return only the final answer. Do not expose private reasoning, raw retrieval
  context, tool calls, or tool-call internals.
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
