'''
chroma db : vector store
it creates the vector store and stores the embeddings in it locally
sqlite3 is created in the current directory

each chunk has 4 things
id : unique id for each chunk
text : the text of the chunk
embedding : the embedding vector of the chunk
metadata : extra information about the chunk like source, page number etc
'''
import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from dotenv import load_dotenv
load_dotenv(override=True)

PDF_PATH = "/Volumes/Work/Oracle_5_8/word2vecpaper.pdf"
DB_DIR = "./chroma_oracle_db"
COLLECTION = "word2vecpaper"

# create document loader
docs = PyPDFLoader(PDF_PATH).load()
print(f"Loaded {len(docs)} documents from {PDF_PATH}")
# create text splitter
text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=140)
chunks = text_splitter.split_documents(docs)
print(f"Created {len(chunks)} chunks from documents")

# our own ids
ids = [ f"chunk_{i}" for i in range(len(chunks))]

embedding = OpenAIEmbeddings(model="text-embedding-3-large")

# define the vector store
vector_store = Chroma(
    collection_name = COLLECTION,
    embedding_function = embedding,
    persist_directory = DB_DIR
)

# send each chunk to the Open AI for embedding and store it in the vector store
vector_store.add_documents(chunks, ids=ids)
print("Chunks stored in Chroma : ", len(vector_store.get()["ids"]))

# read 3 chunks from the vector store
stored = vector_store.get(limit=3, include=["metadatas", "documents", "embeddings"])

for i in range(len(stored["ids"])):
    vector = stored["embeddings"][i]
    print(f"Chunk {i} :")
    print("ID : ", stored["ids"][i])
    print("Text : ", stored["documents"][i])
    print("Metadata : ", stored["metadatas"][i])
    print("Embedding length : ", len(vector))
    print("Vectors: ", vector[:10])  # print first 10 elements of the vector
    print("="*60)