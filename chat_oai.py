# chat models

from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv(override=True)
import os
api_key = os.getenv("OPENAI_API_KEY")

model = ChatOpenAI(
    model = "gpt-4o",
    max_tokens= 500, # None means there is no upper cap on the number of tokens in the response
    openai_api_key=api_key
)

# apply the model , .invoke()
result = model.invoke("Can you tell me something about Oracle Corporation?")

# print(result) # prints the content and metadata of the response

print(result.content) # prints only the content of the response