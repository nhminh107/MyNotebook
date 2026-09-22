import base64
import json
import logging
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path

from ddgs import DDGS
from ddgs.exceptions import DDGSException
from dotenv import load_dotenv
from langchain_community.agent_toolkits.load_tools import load_tools
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langchain.tools import ToolRuntime

from BackEnd.app.database.qdrant_manager import QDrant
from BackEnd.app.text_input.Embedding import EmbeddingModel

load_dotenv()

logger = logging.getLogger(__name__)

WEB_SEARCH_BACKENDS = ("duckduckgo", "brave", "google", "startpage")
WEB_SEARCH_MAX_RESULTS = 5
WEB_SEARCH_TIMEOUT_SECONDS = 10


@dataclass
class AppContext:
    user_id: str
    chat_id: str


class ToolList:
    def __init__(self, llm, qdrant: QDrant, embedding_model: EmbeddingModel):
        self.qdrant = qdrant
        self.embedding_model = embedding_model
        self.ocr_llm = None
        self.tools = load_tools(["llm-math"], llm=llm)
        self.tools.append(
            StructuredTool.from_function(
                func=self._qdrant_query_tool,
                name="qdrant_query",
                description=(
                    "Search the user's uploaded documents for passages relevant "
                    "to a focused query. Use this for document-based questions. "
                    "Results are raw extracted text and may require synthesis and "
                    "format cleanup before answering."
                ),
            )
        )
        self.tools.append(
            StructuredTool.from_function(
                func=self._ocr_image_tool,
                name="ocr_image",
                description="Extract all visible text from a local image file.",
            )
        )
        self._search_tool()

    def _search_tool(self):
        self.tools.append(
            StructuredTool.from_function(
                func=self._web_search_tool,
                name="web_search",
                description=(
                    "Search the public web for current or external information. "
                    "The tool automatically tries multiple search backends and "
                    "returns structured titles, snippets, and URLs."
                ),
            )
        )

    def _web_search_tool(
        self,
        query: str,
        max_results: int = WEB_SEARCH_MAX_RESULTS,
    ) -> str:
        """Search multiple web backends without aborting the agent on network errors."""
        query = query.strip()
        if not query:
            return json.dumps(
                {"status": "invalid_query", "message": "Search query is empty."}
            )

        result_limit = max(1, min(max_results, 10))
        attempted_backends = []

        for backend in WEB_SEARCH_BACKENDS:
            attempted_backends.append(backend)
            try:
                results = self._search_backend(query, backend, result_limit)
            except DDGSException as exc:
                logger.warning(
                    "Web search backend failed: backend=%s error_type=%s",
                    backend,
                    type(exc).__name__,
                )
                continue

            if not results:
                logger.info("Web search backend returned no results: backend=%s", backend)
                continue

            return json.dumps(
                {
                    "status": "ok",
                    "backend": backend,
                    "results": [
                        {
                            "title": result.get("title", ""),
                            "snippet": result.get("body", ""),
                            "url": result.get("href", ""),
                        }
                        for result in results
                    ],
                },
                ensure_ascii=False,
            )

        logger.warning(
            "All web search backends failed or returned no results: backends=%s",
            ",".join(attempted_backends),
        )
        return json.dumps(
            {
                "status": "unavailable",
                "message": (
                    "Web search is temporarily unavailable. Continue with other "
                    "available tools and clearly state any missing information."
                ),
                "attempted_backends": attempted_backends,
            }
        )

    def _search_backend(
        self,
        query: str,
        backend: str,
        max_results: int,
    ) -> list[dict]:
        """Run one DDGS backend so failures can fall through to the next one."""
        with DDGS(timeout=WEB_SEARCH_TIMEOUT_SECONDS) as search_client:
            return search_client.text(
                query,
                region="wt-wt",
                safesearch="moderate",
                timelimit=None,
                max_results=max_results,
                backend=backend,
            )

    def _qdrant_query_tool(self, query: str, runtime: ToolRuntime[AppContext], limit: int = 5) -> str:
        """Return the most relevant passages from the user's documents."""
        query_embedding = self.embedding_model.embed_query(query)
        user_id = runtime.context.user_id
        chat_id = runtime.context.chat_id
        
        return self.qdrant.search(
            user_id=user_id,
            query_text=query,
            query_embedding=query_embedding,
            chat_id=chat_id,
            limit=limit,
        )

    def _ocr_image_tool(self, image_path: str) -> str:
        """Extract all visible text from a local image."""
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {image_path}")

        mime_type, _ = mimetypes.guess_type(path.name)
        if not mime_type or not mime_type.startswith("image/"):
            raise ValueError(f"Unsupported image file: {image_path}")

        api_key = os.getenv("OCR_API_KEY")
        

        if self.ocr_llm is None:
            self.ocr_llm = ChatOpenAI(
                model="mimo-v2.5-free",
                base_url="https://api.mintrouter.ai/v1",
                api_key=api_key,
                temperature=0,
            )

        image_base64 = base64.b64encode(path.read_bytes()).decode("utf-8")
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": "Extract all visible text from this image. Return only the extracted text.",
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_base64}",
                    },
                },
            ]
        )

        response = self.ocr_llm.invoke([message])
        return response.content if isinstance(response.content, str) else str(response.content)
