from langchain_community.document_loaders import PyPDFLoader

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

'''
we took a 12 pager pdf 
created document objects using pypdfloader
12 Document objects were created
and now we are going to chunk them 
'''