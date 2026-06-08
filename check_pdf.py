from langchain_community.document_loaders import PyPDFLoader

pdf_path = r'C:\Users\liner\Desktop\Diplom\mr-osnovy-algoritmizatsii-i-programm.pdf'
loader = PyPDFLoader(pdf_path)
pages = loader.load()

with open('pdf_structure.txt', 'w', encoding='utf-8') as f:
    for i in range(min(15, len(pages))):
        f.write(f"--- Page {i+1} ---\n")
        f.write(pages[i].page_content[:2000] + "\n")
