'''
blog writer agent :
'''
import os 
from dotenv import load_dotenv
load_dotenv(override=True)

from crewai import Agent, Task ,Crew
from crewai_tools import WebsiteSearchTool

# create the tool object
search_tool = WebsiteSearchTool()

# define the agent
writer_agent = Agent(
    role = "blog writer agent",
    goal = "Write short, clear blog posts for social media based on latest research",
    backstory ="You can explain complex concepts with ease and simple analogies",
    llm = "gpt-4o",
    tools = [search_tool] # add the tool to the agent
)

# define the task
write_task = Task(
    description ="Write a 350 word blog post about the {topic}",
    expected_output = "A blog post for Linkedin , with clickable title, 4 paragraphs.",
    agent = writer_agent # assign the agent to the task
)

# assemble the crew
crew = Crew(
    agents= [writer_agent],
    tasks = [write_task],
    verbose = True
)

# execute
result = crew.kickoff(inputs = {"topic" : ":Latest investments by Oracle in 2026"})

print(result)