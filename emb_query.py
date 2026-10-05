from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
load_dotenv(override=True)
import os
api_key = os.getenv("OPENAI_API_KEY")


embedding = OpenAIEmbeddings(
    model = "text-embedding-3-small",
    dimensions = 50,
    api_key=api_key
)

# embed a text string
text = "Oracle Corporation is an American multinational computer technology corporation headquartered in Austin, Texas. The company sells database software and technology, cloud engineered systems, \
    and enterprise software products—particularly its own brands"
    
embedding_vector = embedding.embed_query(text)
print(embedding_vector) # prints the embedding vector
print(len(embedding_vector)) # prints the length of the embedding vector