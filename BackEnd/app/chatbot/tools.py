import base64
import mimetypes
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.agent_toolkits.load_tools import load_tools
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langchain.tools import tool, ToolRuntime
from BackEnd.app.database.qdrant_manager import QDrant
from BackEnd.app.text_input.Embedding import EmbeddingModel
from dataclasses import dataclass
load_dotenv()

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
                description="Search the user's uploaded documents for relevant information.",
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
        search_tool = DuckDuckGoSearchResults(
            name="duckduck",
            description=(
                "Search the public web for information that is not available "
                "in the user's uploaded documents."
            ),
        )
        self.tools.append(search_tool)

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
