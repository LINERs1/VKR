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

# ---------------------------------------------------------------------------
# Prompt — подставляется имя ассистента и курса из .env
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = (
    "### РОЛЬ\n"
    "Ты — профессиональный образовательный ассистент {assistant}. Твоя цель — помогать студенту в освоении курса «{course}».\n\n"
    "### ПРАВИЛА ВЗАИМОДЕЙСТВИЯ\n"
    "1. ОТВЕТЫ: Будь вежливым, лаконичным и вдохновляющим. Отвечай строго на русском языке.\n"
    "2. КОНТЕКСТ: Используй предоставленные материалы курса для ответов. Если информации нет в контексте, честно скажи об этом, но предложи общие знания по теме, если они полезны.\n"
    "3. СТИЛЬ: Твои ответы предназначены для озвучки, поэтому избегай сложных таблиц и громоздких формул. Используй простую и понятную речь.\n\n"
    "### НАВИГАЦИЯ (СИСТЕМНЫЕ КОМАНДЫ)\n"
    "{page_info}\n"
    "- Если пользователь просит открыть другой курс из списка выше, добавь в САМЫЙ КОНЕЦ ответа тег: [NAVIGATE:/courses/ID].\n"
    "- Если просит вернуться на главную: [NAVIGATE:/].\n"
    "- ВАЖНО: Используй ТОЛЬКО те теги, которые указаны в списке выше. Не придумывай свои пути.\n"
    "- Если курса нет в списке, не используй тег, просто скажи, что курс пока недоступен.\n\n"
    "### КОНТЕКСТ КУРСА\n"
    "{context}\n\n"
    "### ДИАЛОГ\n"
    "{history}\n"
    "Студент: {question}\n"
    "Ответ {assistant}:"
)

_GLOBAL_PROMPT_TEMPLATE = (
    "### РОЛЬ\n"
    "Ты — интеллектуальный гид EduAI по имени {assistant}. Ты помогаешь пользователям ориентироваться на платформе и выбирать лучшие образовательные курсы.\n\n"
    "### ПРАВИЛА\n"
    "1. ЯЗЫК: Отвечай только на русском. Никаких иероглифов или англицизмов без необходимости.\n"
    "2. ПОМОЩЬ: Рассказывай о преимуществах платформы и помогай подобрать курс под интересы пользователя.\n"
    "3. ЛАКОНИЧНОСТЬ: Говори кратко и по существу.\n\n"
    "### НАВИГАЦИЯ\n"
    "{page_info}\n"
    "- Если пользователь определился с выбором или просит открыть курс, добавь в КОНЕЦ ответа: [NAVIGATE:/courses/ID].\n"
    "- Используй ТОЛЬКО готовые теги из списка. Не галлюцинируй пути.\n\n"
    "### ДИАЛОГ\n"
    "{history}\n"
    "Пользователь: {question}\n"
    "Ответ {assistant}:"
)


# ---------------------------------------------------------------------------
# Cached singletons — один инстанс эмбеддингов и хранилища на процесс
# ---------------------------------------------------------------------------

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
        return OllamaEmbeddings(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.EMBEDDING_MODEL,
            client_kwargs={"headers": {"ngrok-skip-browser-warning": "true"}},
        )

    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER}")


@lru_cache(maxsize=16)
def get_vector_store(course_id: str = "default") -> Chroma:
    """
    Возвращает Chroma-хранилище для конкретного курса.
    Каждый course_id → отдельная коллекция в той же БД.
    LRU-кеш на 16 курсов.
    """
    collection_name = f"{settings.CHROMA_COLLECTION}_{course_id}"
    logger.info(f"Vector store: collection='{collection_name}'")
    return Chroma(
        persist_directory=settings.CHROMA_PERSIST_DIR,
        embedding_function=get_embeddings(),
        collection_name=collection_name,
    )


# ---------------------------------------------------------------------------
# Retriever & chain
# ---------------------------------------------------------------------------

def get_retriever(course_id: str = "default"):
    return get_vector_store(course_id).as_retriever(search_kwargs={"k": 4})


def get_chain(course_name: str = None, course_id: str = "default", page_context: dict = {}):
    """Prompt + LLM + parser — без retriever внутри."""
    name = course_name if course_name else settings.COURSE_NAME
    is_global = course_id == "default"
    template = _GLOBAL_PROMPT_TEMPLATE if is_global else _PROMPT_TEMPLATE

    # Формируем текстовый блок с инфо о странице и курсах
    page_info_parts = []
    available = page_context.get("available_courses", [])
    if available:
        courses_lines = "\n".join(
            f"  - {c.get('icon','')} {c.get('title', '')}. Для перехода используй тег: [NAVIGATE:/courses/{c.get('id','')}]".strip()
            for c in available
        )
        page_info_parts.append(f"Доступные курсы и команды перехода:\n{courses_lines}")
        page_info_parts.append("Для возврата на главную страницу используй тег: [NAVIGATE:/]")

    page_info = ("\n".join(page_info_parts) + "\n\n") if page_info_parts else ""

    prompt = PromptTemplate(
        template=template,
        input_variables=["context", "question", "history"],
        partial_variables={
            "assistant": settings.ASSISTANT_NAME,
            "course": name,
            "page_info": page_info,
        }
    )
    return prompt | get_llm() | StrOutputParser()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_docs(docs: List[Document]) -> str:
    return "\n\n---\n\n".join(
        f"[{doc.metadata.get('source', 'Unknown')}]\n{doc.page_content}"
        for doc in docs
    )


def format_history(history: list[dict]) -> str:
    """Конвертирует [{role, content}] в строку для промпта."""
    if not history:
        return ""
    lines = ["История диалога:"]
    for msg in history:
        role = "Студент" if msg.get("role") == "user" else settings.ASSISTANT_NAME
        lines.append(f"{role}: {msg.get('content', '')}")
    lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Ingest — загрузка и индексация документов курса
# ---------------------------------------------------------------------------

def ingest_documents(directory: str, course_id: str = "default") -> dict:
    """
    Загружает все поддерживаемые документы и индексирует их в ChromaDB.
    Дедупликация по имени файла при повторной загрузке.
    """
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

    LOADERS = {
        ".pdf":  lambda p: PyPDFLoader(p),
        ".docx": lambda p: Docx2txtLoader(p),
        ".txt":  lambda p: TextLoader(p, encoding="utf-8"),
        ".md":   lambda p: TextLoader(p, encoding="utf-8"),
    }

    documents = []
    store = get_vector_store(course_id)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

    for file_path in Path(directory).rglob("*"):
        ext = file_path.suffix.lower()
        if ext not in LOADERS:
            continue
        try:
            # Check if it already exists
            existing = store._collection.get(where={"source": file_path.name})
            if existing and existing.get("ids") and len(existing["ids"]) > 0:
                logger.info(f"Skipping already ingested file: {file_path.name}")
                continue
                
            # If we want to force re-ingest, we would delete here, but for free tier we skip
            # store._collection.delete(where={"source": file_path.name})
            
            docs = LOADERS[ext](str(file_path)).load()
            for d in docs:
                d.metadata["source"] = file_path.name
                d.metadata["course_id"] = course_id

            chunks = text_splitter.split_documents(docs)
            store.add_documents(chunks)
            documents.extend(chunks)
            logger.info(f"Loaded: {file_path.name} (course={course_id})")
        except Exception as e:
            logger.error(f"Error loading {file_path.name}: {e}")

    if not documents:
        return {"status": "warning", "message": "No documents found", "chunks": 0}

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(documents)
    store.add_documents(chunks)

    logger.info(f"Indexed {len(chunks)} chunks from {len(documents)} pages (course={course_id})")
    return {"status": "success", "documents": len(documents), "chunks": len(chunks)}
