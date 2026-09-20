from langchain_core.prompts import PromptTemplate
from langchain_classic.memory import ConversationSummaryMemory
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_classic.chains.llm import LLMChain
load_dotenv()

MINTROUTE_API = os.getenv("LLM_API_KEY")

class Chatbot: 
    def __init__(self):

        self._system_prompt = """Use the retrieval information to answer the user's question.
        The retrieval information is ordered from most relevant to least relevant.
        If the information is missing or insufficient, clearly say so.
        Do not make claims that are not supported by the provided information.

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

        self._prompt_template = PromptTemplate(
            template=self._system_prompt,
            input_variables=["user_prompt", "info"]
        )

        self._summary_template = PromptTemplate(
            template=self._summary_prompt,
            input_variables=["new_lines", "summary"]
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

        self.llm_chain = LLMChain(
            prompt=self._prompt_template,
            llm=self._llm,
            output_key="text",
            memory=self._memory
        )

    def invoke(self, user_prompt: str, data: str):
        payload = {
            "user_prompt": user_prompt, 
            "info": data
        }
        result = self.llm_chain.invoke(payload)
        return result['text']


if __name__ == "__main__": 
    chatbot = Chatbot()
    user_prompt = "Ai là ca sĩ số 1 Việt Nam"
    data = """Jack đánh bại Sơn Tùng về số lượt view trên Youtube; Sóng gió của Jack vượt Hãy Trao Cho Anh của Sơn Tùng; 
    ; Jack là nghệ sĩ duy nhất ở Việt Nam có 3 hit trên 300 triệu views
    """
    ans = chatbot.invoke(user_prompt=user_prompt, data=data)
    print(ans)



