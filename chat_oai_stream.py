# chat models

from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv(override=True)
import os
api_key = os.getenv("OPENAI_API_KEY")

model = ChatOpenAI(
    model = "gpt-4o",
    max_tokens= None, # None means there is no upper cap on the number of tokens in the response
    openai_api_key=api_key,
    streaming = True
)

for result in model.stream("Can you tell me something about Oracle Corporation?"):
    print(result.content, end="", flush=True) # prints only the content of the response