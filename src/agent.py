# agent.py
from langchain.chat_models import init_chat_model
from langchain.agents import initialize_agent, AgentType
from langchain.tools import tool
import inference

def build_llm():
    return init_chat_model("gpt-4o-mini", model_provider="openai")

def make_retrieve_tool(collection):
    @tool("retrieve")
    def retrieve_tool(query: str):
        """Search the indexed repo files and return top matches."""
        return inference.retrieve(collection, query)
    return retrieve_tool

def build_agent(llm, tools):
    return initialize_agent(tools=tools, llm=llm, agent=AgentType.OPENAI_FUNCTIONS, verbose=True)
