import logging
from functools import lru_cache
from pathlib import Path
from typing import List

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.services.llm_service import get_llm

logger = logging.getLogger(__name__)

_STRICT_PROMPT_TEMPLATE = (
    "### ЯЗЫК\n"
    "ВСЕГДА отвечай ТОЛЬКО на русском языке.\n\n"
    "### КТО ТЫ\n"
    "Ты — {assistant}, умный ИИ-помощник, который отвечает на вопросы пользователей.\n"
    "Ты обязан основывать свои ответы на методичках курса '{course_id}'.\n\n"
    "### ПРАВИЛА (СТРОГО)\n"
    "1. Твоя ГЛАВНАЯ задача: искать ответ в предоставленном КОНТЕКСТЕ из методички.\n"
    "2. Если в КОНТЕКСТЕ есть информация, полностью опирайся на неё.\n"
    "3. Если информации в КОНТЕКСТЕ нет, вежливо откажись отвечать и скажи, что ты можешь отвечать только на вопросы по материалам курса. НИКОГДА не используй свои общие знания для ответа на вопросы вне курса.\n"
    "4. Отвечай дружелюбно, лаконично (2-3 абзаца).\n"
    "5. Если с тобой просто здороваются, поздоровайся в ответ.\n\n"
    "### МАТЕРИАЛЫ КУРСА (КОНТЕКСТ)\n"
    "{context}\n\n"
    "### ИСТОРИЯ ЧАТА\n"
    "{history}\n"
    "Вопрос пользователя: {question}\n"
    "{assistant}:"
)

@lru_cache(maxsize=1)
def get_embeddings():
    if settings.EMBEDDING_PROVIDER == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
        )
    if settings.EMBEDDING_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.OPENAI_API_KEY,
        )
    if settings.EMBEDDING_PROVIDER == "ollama":
        from langchain_ollama import OllamaEmbeddings
        ollama_client = {"trust_env": False}
        return OllamaEmbeddings(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.EMBEDDING_MODEL,
            client_kwargs=ollama_client,
            sync_client_kwargs=ollama_client,
            async_client_kwargs=ollama_client,
        )
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER}")

@lru_cache(maxsize=16)
def get_vector_store(course_id: str) -> Chroma:
    collection_name = f"{settings.CHROMA_COLLECTION}_{course_id}"
    logger.info(f"Vector store: collection='{collection_name}'")
    return Chroma(
        persist_directory=settings.CHROMA_PERSIST_DIR,
        embedding_function=get_embeddings(),
        collection_name=collection_name,
    )

def get_retriever(course_id: str):
    return get_vector_store(course_id).as_retriever(search_kwargs={"k": 4})

def get_chain(course_id: str):
    prompt = PromptTemplate(
        template=_STRICT_PROMPT_TEMPLATE,
        input_variables=["context", "question", "history"],
        partial_variables={
            "assistant": settings.ASSISTANT_NAME,
            "course_id": course_id,
        },
    )
    return prompt | get_llm() | StrOutputParser()

def format_docs(docs: List[Document]) -> str:
    if not docs:
        return "(материалы курса не найдены в поисковой выдаче)"
    return "\n\n---\n\n".join(
        f"[{doc.metadata.get('source', 'Unknown')}]\n{doc.page_content}"
        for doc in docs
    )

def format_history(history: list[dict]) -> str:
    if not history:
        return ""
    lines = []
    for msg in history[-6:]:
        role = "Пользователь" if msg.get("role") == "user" else settings.ASSISTANT_NAME
        content = msg.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) + "\n" if lines else ""

def _indexed_source_exists(store: Chroma, source_name: str) -> bool:
    try:
        if hasattr(store, "get"):
            existing = store.get(where={"source": source_name})
            ids = existing.get("ids") if isinstance(existing, dict) else None
            if ids and len(ids) > 0:
                return True
    except Exception:
        pass
    return False

def _clear_vector_store_cache() -> None:
    get_vector_store.cache_clear()

def ingest_documents(directory: str, course_id: str) -> dict:
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
    LOADERS = {
        ".pdf":  lambda p: PyPDFLoader(p),
        ".docx": lambda p: Docx2txtLoader(p),
        ".txt":  lambda p: TextLoader(p, encoding="utf-8"),
        ".md":   lambda p: TextLoader(p, encoding="utf-8"),
    }
    store = get_vector_store(course_id)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    total_chunks = 0
    total_docs = 0

    for file_path in Path(directory).rglob("*"):
        ext = file_path.suffix.lower()
        if ext not in LOADERS:
            continue
        try:
            if _indexed_source_exists(store, file_path.name):
                continue
            docs = LOADERS[ext](str(file_path)).load()
            for d in docs:
                d.metadata["source"] = file_path.name
                d.metadata["course_id"] = course_id
            chunks = text_splitter.split_documents(docs)
            if chunks:
                store.add_documents(chunks)
                total_chunks += len(chunks)
                total_docs += len(docs)
        except Exception as e:
            logger.error(f"Ошибка загрузки {file_path.name}: {e}")

    if total_chunks > 0:
        _clear_vector_store_cache()
        return {"status": "success", "documents": total_docs, "chunks": total_chunks}
    return {"status": "warning", "message": "Новых документов нет", "chunks": 0, "documents": 0}
