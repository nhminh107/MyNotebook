from collections.abc import Iterator
import os

from dotenv import load_dotenv
from langchain_classic.chains.llm import LLMChain
from langchain_classic.memory import ConversationSummaryMemory
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

MINTROUTE_API = os.getenv("LLM_API_KEY")

class Chatbot: 
    def __init__(self):

        self._system_prompt = """Use the retrieval information to answer the user's question.
        The retrieval information is ordered from most relevant to least relevant.
        If the information is missing or insufficient, clearly say so.
        Do not make claims that are not supported by the provided information.
        Format the answer as clear Markdown when structure improves readability.

        Conversation summary:{chat_history}
        The user's question: {user_prompt}
        Retrieval information: {info}
        """

        self._summary_prompt = """<s><|user|>Summarize the conversations and update with the new lines.
        Current summary: 
        {summary}
        new lines of conversation:
        {new_lines}
        New summary:<|end|>
        <|assistant|>
        """

        self._convert_prompt = """Use the conversation summary to convert user's prompt. The converted prompt must be clearly, useful for the LLM. 
        For example, user prompt: "Nó nhằm mục đích gì trong hệ thống RAG", in the conversation summary have information about "vector database", 
        so that converted prompt should be: "VectorDB nhằm mục đích gì trong hệ thống RAG".
        User prompt: {user_prompt}
        Conversation summary: {chat_history}"""


        self._prompt_template = PromptTemplate(
            template=self._system_prompt,
            input_variables=["user_prompt", "info"]
        )

        self._summary_template = PromptTemplate(
            template=self._summary_prompt,
            input_variables=["new_lines", "summary"]
        )

        self._convert_template = PromptTemplate(
            template=self._convert_prompt,
            input_variables=["user_prompt", "chat_history"]
        )
        self._summary_llm = ChatOpenAI(
            model="nemotron-3-ultra-free",
            temperature=0.1,
            base_url="https://api.mintrouter.ai/v1",
            api_key=MINTROUTE_API,
            streaming=True
        )
        self._llm = ChatOpenAI(
            model="deepseek-4.1",
            temperature=0.1,
            base_url="https://api.mintrouter.ai/v1",
            api_key=MINTROUTE_API,
            streaming=True
        )
        self._memory = ConversationSummaryMemory(
            llm=self._llm, 
            memory_key="chat_history",
            input_key="user_prompt",
            output_key="text",
            prompt=self._summary_template
        )

        self._summary_chain = LLMChain(
            prompt=self._summary_template, 
            llm=self._summary_llm,
            output_key="summary"
        )
        self._convert_chain = LLMChain(
            prompt=self._convert_template,
            llm=self._llm,
            output_key="converted_query",
        )

        self.llm_chain = LLMChain(
            prompt=self._prompt_template,
            llm=self._llm,
            output_key="text",
            memory=self._memory
        )

    def summarize_conversation(self, current_summary: str, user_message: str, chatbot_message: str): 
        new_lines = (
            f"User: {user_message}\n"
            f"Chatbot: {chatbot_message}"
        )
        result = self._summary_chain.invoke({
            "summary": current_summary,
            "new_lines": new_lines
        })
        return result["summary"].strip()
    def convert_query(self, user_prompt: str) -> str:
        chat_history = self._memory.load_memory_variables({})["chat_history"]
        if not chat_history:
            return user_prompt
        result = self._convert_chain.invoke(
            {
                "user_prompt": user_prompt,
                "chat_history": chat_history,
            }
        )
        return result["converted_query"].strip()
    
    def invoke(self, user_prompt: str, data: str, memory: str, mode: int = 0):
        # Mode = 1: Convert query
        if mode == 0: 
            payload = {
                "user_prompt": user_prompt, 
                "info": data,
                "chat_history": memory
            }
            result = self.llm_chain.invoke(payload)
            return result['text']

        converted_query = self.convert_query(user_prompt)
        payload = {
            "user_prompt": converted_query, 
            "info": data,
            "chat_history": memory
        }

        result = self.llm_chain.invoke(payload)
        return result['text']

    def stream(self, user_prompt: str, data: str, memory: str) -> Iterator[str]:
        """Yield response text chunks and save the completed turn to memory."""
        prompt = self._prompt_template.format_prompt(
            user_prompt=user_prompt,
            info=data,
            chat_history=memory
        )

        for chunk in self._llm.stream(prompt):
            text = str(chunk.text)
            yield text



if __name__ == "__main__": 
    chatbot = Chatbot()
    user_prompt = "Ai là ca sĩ số 1 Việt Nam"
    data = """Jack đánh bại Sơn Tùng về số lượt view trên Youtube; Sóng gió của Jack vượt Hãy Trao Cho Anh của Sơn Tùng; 
    ; Jack là nghệ sĩ duy nhất ở Việt Nam có 3 hit trên 300 triệu views
    """
    ans = chatbot.invoke(user_prompt=user_prompt, data=data)
    print(ans)


