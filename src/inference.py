# # inference.py
# from typing import List, Dict, Any
# import chromadb
# from chromadb.utils import embedding_functions

# def get_or_create_collection(db_path: str, name: str):
#     client = chromadb.PersistentClient(path=db_path)
#     ef = embedding_functions.SentenceTransformerEmbeddingFunction("all-MiniLM-L6-v2")
#     return client.get_or_create_collection(name=name, embedding_function=ef)

# def index_files(collection, code_list: List[str], names: List[str]) -> None:
#     docs, metas, ids = [], [], []
#     for content, name in zip(code_list, names):
#         if name.endswith((".py", ".md", ".txt")):
#             text = content if isinstance(content, str) else content.decode("utf-8", errors="ignore")
#             docs.append(text)
#             metas.append({"source": name})
#             ids.append(name)
#     if docs:
#         collection.add(documents=docs, metadatas=metas, ids=ids)

# def retrieve(collection, query: str, n_results: int = 3) -> Dict[str, Any]:
#     return collection.query(query_texts=query, n_results=n_results)


# inference.py
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions

def get_or_create_collection(db_path: str, name: str):
    client = chromadb.PersistentClient(path=db_path)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction("all-MiniLM-L6-v2")
    return client.get_or_create_collection(name=name, embedding_function=ef)

def index_files(collection, code_list: List[str], names: List[str]) -> int:
    """
    Index documents; returns number of docs added.
    Safe if lists are empty/mismatched.
    """
    if not code_list or not names:
        return 0
    n = min(len(code_list), len(names))
    docs = code_list[:n]
    metas = [{"source": nm} for nm in names[:n]]
    ids = []
    # Ensure unique ids (Chroma requires uniqueness)
    for i, nm in enumerate(names[:n]):
        ids.append(f"{nm}::{i}")
    collection.add(documents=docs, metadatas=metas, ids=ids)
    return n

def retrieve(collection, query: str, n_results: int = 3) -> Dict[str, Any]:
    return collection.query(query_texts=query, n_results=n_results)
