from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
load_dotenv(override=True)
import os
api_key = os.getenv("OPENAI_API_KEY")


embedding = OpenAIEmbeddings(
    model = "text-embedding-3-large",
    dimensions = 50,
    api_key=api_key
)

documents = [
    """
    Oracle Corporation is one of the world's largest enterprise software companies,
    founded in 1977 by Larry Ellison, Bob Miner, and Ed Oates. The company is best
    known for its relational database management systems, which power mission-critical
    applications for businesses across industries. Over the years, Oracle has expanded
    its portfolio to include cloud computing, enterprise resource planning (ERP),
    customer relationship management (CRM), and supply chain management solutions.
    Today, Oracle serves thousands of organizations globally, helping them manage
    data, automate processes, and improve business decision-making.
    """,

    """
    Oracle Cloud Infrastructure (OCI) is the company's cloud computing platform,
    designed to provide scalable, secure, and high-performance cloud services.
    OCI offers services across computing, storage, networking, databases, analytics,
    artificial intelligence, and machine learning. Organizations use OCI to modernize
    legacy applications, run data-intensive workloads, and accelerate digital
    transformation initiatives. Oracle's cloud strategy emphasizes performance,
    security, and cost efficiency, making it a competitive alternative to other
    major cloud providers.
    """,

    """
    In recent years, Oracle has invested heavily in artificial intelligence and
    autonomous technologies. Products such as the Autonomous Database automate
    routine administrative tasks like patching, tuning, and backups, reducing
    operational overhead for organizations. Oracle has also integrated generative
    AI capabilities into its business applications, enabling users to automate
    workflows, generate insights, and enhance productivity. These innovations
    position Oracle as a key player in the rapidly evolving enterprise AI landscape.
    """
]

result = embedding.embed_documents(documents)
print(result)

