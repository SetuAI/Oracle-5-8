# for chunking
# recursive character text splitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# create the loader object
loader = PyPDFLoader("/Volumes/Work/Oracle_5_8/word2vecpaper.pdf")

# create the document objects
docs = loader.load()

# print Dos
print(docs)
print("="*60)
print(len(docs)) # prints the number of documents loaded
# extract first document object
print("First document object:\n")
print(docs[0]) # prints the first document object
print("Document objects are created....\n")

print("Starting the chunking process....\n")

# create the text splitter object
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size = 300,
    chunk_overlap = 140
)

# apply text splitter to the document objects
chunks = text_splitter.split_documents(docs)

print("Chunks created:\n")
print(len(chunks))
# pick out any chunk 
print("First chunk:" , chunks[0].page_content) # prints the first chunk
