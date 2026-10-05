# prompt template : 
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv(override=True)
import os
import streamlit as st
from langchain_core.prompts import PromptTemplate, load_prompt

model = ChatOpenAI()

# streamlit ui code
st.header("Research Tool")

# user inputs
paper_input = st.selectbox("Select the Research Paper name: ", ["Attention Is All You Need",
                                                            "BERT: Pre-training of Deep Bidirectional Transformers", 
                                                            "GPT-3: Language Models are Few-Shot Learners", 
                                                            "Diffusion Models Beat GANs on Image Synthesis"] )
style_input = st.selectbox("Select the explanation style: ", ["Beginner-Friendly",
                                                              "Technical",
                                                              "Code-Oriented",
                                                              "Mathematical"]) 
length_input = st.selectbox("Select the explanation length: ", ["Short (1-2 paragraphs)",
                                                                "Medium (3-5 paragraphs)",
                                                                "Long (detailed explanation)"])


template = PromptTemplate(
    template = """
    Please summarize the research paper titled {paper_input} with the following specifications:
    Explanation Style : {style_input}
    Explanation Length : {length_input}
    1. Mathematical Details : 
    - Include all the relevant math equations if present in the paper
    explain the math concepts using simple, intuitive code snippets where applicable
    2. analogies :
    Use relatable analogies to simplify complex ideas
    If certain info is not available in the paper, respond with : 
    Insufficient info available.
    Ensure the summary is clear, accurate and aligned with style and length given by user
    """,
    input_variables = ["paper_input","style_input","length_input"]
)

prompt = template.invoke({
    'paper_input' : paper_input,
    'style_input' : style_input,
    'length_input' : length_input
})

# invoke the model
if st.button("Summarize"):
    result = model.invoke(prompt)
    st.write(result.content)

