import os
import ast
import requests
import chromadb
from fpdf import FPDF
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from chromadb.utils import embedding_functions
from langchain.agents import initialize_agent, AgentType

from dotenv import load_dotenv
load_dotenv()

llm = ChatOpenAI(
    model="gpt-4o-mini", 
    temperature=0,
    api_key=os.environ["OPENAI_API_KEY"]
    )

@tool
def github_tool(repo_url):
    
    """
        This tool is used to extract file hirarchy from a github repo
    """

    try:
        parts = repo_url.rstrip('/').split('/')
        owner, repo = parts[-2], parts[-1]
    except:
        raise ValueError("Invalid GitHub URL")

    def fetch_tree(owner, repo, path=""):
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch contents: {response.json().get('message', 'Unknown error')}")

        contents = response.json()
        hierarchy = {}

        for item in contents:
            if item['type'] == 'dir':
                hierarchy[item['name']] = fetch_tree(owner, repo, item['path'])
            else:
                hierarchy[item['name']] = None
        return hierarchy

    return fetch_tree(owner, repo)

@tool
def retrive(query: str, db_path: str):

    """
    To retrieve data from vector db.
    db_path is simply the repo url.
    """

    if not os.path.exists(db_path):
        return "Repo not analysed yet"

    # 1. init Chroma (persistent storage)
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(
        name="repo_files",
        embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction("all-MiniLM-L6-v2")
)

    res = collection.query(query_texts = query, n_results=2)
    print(res["documents"][0][0])   # print top result text
    print(res["metadatas"][0][0])   # file info
    return res

@tool
def generate_pdf(filename: str, body: str) -> str:
    """Create a PDF file. Call this tool whenever the user asks for a PDF."""
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    os.makedirs("exports", exist_ok=True)
    path = os.path.join("exports", filename)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in body.split("\n"):
        pdf.multi_cell(0, 8, line)
    pdf.output(path)
    return path


def analyse_repo_(repo_url_: str):
    agent = initialize_agent(
        tools=[retrive, github_tool, generate_pdf],
        llm = llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True
    )

    query = repo_url_

    instruction = (
        'Return ONLY a valid Python list of repository file paths (strings). '
        'No extra words, no code fences. Use the "github_tool" to enumerate the repo. '
        f'Repository URL: {query}'
    )


    response = agent.run(instruction)

    lst = ast.literal_eval(response)
    print(lst)  


    def fetch_github_file(repo_url: str, file_path: str) -> str:
        """
        Fetch raw code content from a GitHub file path.
        repo_url = https://github.com/user/repo  (NOT the blob link)
        file_path = relative path in the repo (e.g., "Train_model.py")
        """
        if not repo_url.endswith("/"):
            repo_url += "/"
        
        # Assume default branch = main (change if your repo uses 'master')
        raw_url = repo_url.replace("github.com", "raw.githubusercontent.com") + "main/" + file_path
        
        response = requests.get(raw_url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch {file_path}: {response.status_code}")
        
        return response.text


    def fetch_multiple_files(repo_url: str, file_paths: list[str]) -> list[str]:
        codes = []
        for path in file_paths:
            try:
                code = fetch_github_file(repo_url, path)
                codes.append(code)
                print(f"Fetched: {path}")
            except Exception as e:
                print(f"Error fetching {path}: {e}")
        return codes


    code_list = fetch_multiple_files(repo_url = repo_url_, file_paths = lst)

    # 1. init Chroma (persistent storage)
    client = chromadb.PersistentClient(path=repo_url_)
    collection = client.get_or_create_collection(
        name="repo_files",
        embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction("all-MiniLM-L6-v2")
)

    # 2. add only text/code files to Chroma
    for content, name in zip(code_list, lst):
        if name.endswith((".py", ".md", ".txt")):   # skip binaries
            text = content if isinstance(content, str) else content.decode("utf-8", errors="ignore")
            collection.add(
                documents=[text],
                metadatas=[{"source": name}],
                ids=[name]  # unique ID per file
            )
            print(f"✅ Added {name}")
        else:
            print(f"⏩ Skipped {name} (binary)")

    return "Repo analysed successfully"

def question_answering(query: str, repo_url: str):
    agent = initialize_agent(
        tools=[retrive, github_tool, generate_pdf],
        llm = llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True
    )

    prompt = f"Please answer the following query using the retrieve tool. always answer questions with 100 percent confidence. query: ${query} repo_url: ${repo_url}"

    response = agent.run(prompt)

    return response