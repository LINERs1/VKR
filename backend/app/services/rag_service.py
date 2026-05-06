import logging
from pathlib import Path
from typing import List

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.config import settings
from app.services.llm_service import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Ты — образовательный ассистент {assistant} для курса «{course}».
Отвечай ТОЛЬКО на основе контекста из методических материалов ниже.
Если информации недостаточно — честно скажи об этом.
Отвечай кратко, структурированно, на русском языке.

Контекст:
{{context}}

Вопрос студента: {{question}}

Ответ {assistant}:\
""".format(assistant=settings.ASSISTANT_NAME, course=settings.COURSE_NAME)


def get_embeddings():
    if settings.EMBEDDING_PROVIDER == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=settings.EMBEDDING_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )
    if settings.EMBEDDING_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.OPENAI_API_KEY,
        )
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER}")


def get_vector_store() -> Chroma:
    return Chroma(
        persist_directory=settings.CHROMA_PERSIST_DIR,
        embedding_function=get_embeddings(),
        collection_name=settings.CHROMA_COLLECTION,
    )


def format_docs(docs: List[Document]) -> str:
    return "\n\n---\n\n".join(
        f"[{doc.metadata.get('source', 'Unknown')}]\n{doc.page_content}"
        for doc in docs
    )


def get_rag_chain():
    """Returns (chain, retriever) using LCEL with full streaming support."""
    retriever = get_vector_store().as_retriever(search_kwargs={"k": 4})
    prompt = PromptTemplate(
        template=SYSTEM_PROMPT,
        input_variables=["context", "question"],
    )
    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | get_llm()
        | StrOutputParser()
    )
    return chain, retriever


def ingest_documents(directory: str) -> dict:
    """Load all supported documents and index into ChromaDB."""
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

    LOADERS = {
        ".pdf": lambda p: PyPDFLoader(p),
        ".docx": lambda p: Docx2txtLoader(p),
        ".txt": lambda p: TextLoader(p, encoding="utf-8"),
        ".md": lambda p: TextLoader(p, encoding="utf-8"),
    }

    documents = []
    for file_path in Path(directory).rglob("*"):
        ext = file_path.suffix.lower()
        if ext in LOADERS:
            try:
                docs = LOADERS[ext](str(file_path)).load()
                for doc in docs:
                    doc.metadata["source"] = file_path.name
                documents.extend(docs)
                logger.info(f"Loaded: {file_path.name}")
            except Exception as e:
                logger.error(f"Error loading {file_path.name}: {e}")

    if not documents:
        return {"status": "warning", "message": "No documents found", "chunks": 0}

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(documents)
    get_vector_store().add_documents(chunks)

    logger.info(f"Indexed {len(chunks)} chunks from {len(documents)} pages")
    return {"status": "success", "documents": len(documents), "chunks": len(chunks)}
