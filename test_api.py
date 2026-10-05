'''
FAST API backend on top of chroma db 

to run : uvicorn test_api:app --reload
Open : http://127.0.0.1:8000/docs

'''

import os
from fastapi import FastAPI # pip install fastapi # pip install uvicorn
from pydantic import BaseModel
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from dotenv import load_dotenv
load_dotenv(override=True)

PDF_PATH = "/Volumes/Work/Oracle_5_8/word2vecpaper.pdf"
DB_DIR = "./chroma_oracle_db"
COLLECTION = "word2vecpaper"

embedding = OpenAIEmbeddings(model="text-embedding-3-large")


# define the vector store
vector_store = Chroma(
    collection_name = COLLECTION,
    embedding_function = embedding,
    persist_directory = DB_DIR
)

app = FastAPI(title="Word 2 vec paper search")

class SearchRequest(BaseModel):
    query: str
    top_k: int = 3  

@app.get("/chunks")
def list_chunks(limit : int=5):
    "Show the stored chunks with their id, text, embedding"
    stored = vector_store.get(limit=limit, include=["metadatas", "documents", "embeddings"])
    return [
        {
            "id": stored["ids"][i],
            "page": stored["metadatas"][i]["page"],
            "text": stored["documents"][i],
            "embedding_size": len(stored["embeddings"][i]),
            "embedding_first_5": [float(x) for x in stored["embeddings"][i][:5]],
        }
        for i in range(len(stored["ids"]))
    ]
 
@app.post("/search")
def search(request: SearchRequest):
    """Embed the query and return the k closest chunks. Lower distance = closer match."""
    results = vector_store.similarity_search_with_score(request.query, k=request.top_k)
    return [
        {
            "id": doc.id,
            "page": doc.metadata["page"],
            "distance": float(distance),
            "text": doc.page_content,
        }
        for doc, distance in results
    ]
 