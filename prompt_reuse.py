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


template = load_prompt('prompt_oracle.json')

if st.button("Play"): 
    chain = template | model #chain : linear workflow : prompt template -> model
    result = chain.invoke({
    'paper_input' : paper_input,
    'style_input' : style_input,
    'length_input' : length_input
    })
    st.write(result.content)