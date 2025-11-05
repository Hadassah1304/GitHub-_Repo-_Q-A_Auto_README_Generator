from fastapi import FastAPI
from pydantic import BaseModel
from main import analyse_repo_, question_answering


app = FastAPI()

class QueryRequest(BaseModel):
    query: str
    repo_url: str

class AnalyseRequest(BaseModel):
    repo_url: str

@app.post("/analyse_repo")
def analyse_repo(request_body: AnalyseRequest):
    return analyse_repo_(request_body.repo_url)

@app.post("/query")
def handle_query(request_body: QueryRequest):
    # Placeholder for query handling logic
    return question_answering(request_body.query, request_body.repo_url)

@app.get("/hello")
def say_hello():
    return "Hello Hadassah!!"

