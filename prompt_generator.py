from langchain_core.prompts import PromptTemplate

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

template.save("prompt_oracle.json")