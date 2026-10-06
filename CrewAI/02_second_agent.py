'''
2 agents : 
1 searches the website 
2 agent writes a blog
'''

import os
from dotenv import load_dotenv
load_dotenv(override=True)
from crewai import Agent, Task ,Crew, Process
from crewai_tools import WebsiteSearchTool

WEBSITE = "https://www.oracle.com/in/news/"

search_tool = WebsiteSearchTool(website = WEBSITE)


# define the researcher agent

researcher_agent = Agent(
    role = "Website researcher",
    goal = "Search the website for relevant information about the {topic} from the given website",
    backstory = "You only report what you find on the website, and you do not make up any information",
    tools = [search_tool], # researcher agent has access to the search tool
    llm = "gpt-4o",
)


# defining the writer agent
writer_agent = Agent(
    role ="Blog writer",
    goal = "Turn the research notes into a clear blog post for beginners",
    backstory = "You write short , clear blog posts for beginners, and you explain complex \
        technical topics in simple terms with interesting analogies",
    llm = "gpt-4o",

)

# define the research task 

research_task = Task(
    description = "Search the website for relevant information about the {topic} from the given website", 
    expected_output = "5-7 bullet points on the facts found on the website about the topic",
    agent = researcher_agent,
)


# define the write task

write_task = Task(
    description = "Write a 300 word blog post about the {topic} based on the research notes",
    expected_output ="A blog post in markdown with title, introduction, 3-4 short paragraphs, and a conclusion, this is for social media",
    agent = writer_agent,
    context = [research_task],
    output_file = "blog_post.md"
)

# assemble the crew

crew = Crew(
    agents = [researcher_agent, writer_agent],
    tasks = [research_task, write_task],
    process = Process.sequential,
    verbose = True
)

result = crew.kickoff(inputs = {"topic": "extract news with respect to NTT Docomo"})

print(result)