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
# Промпты — ВАЖНО: явное требование отвечать ТОЛЬКО на русском языке
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = (
    "### КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО\n"
    "ОТВЕЧАЙ ИСКЛЮЧИТЕЛЬНО НА РУССКОМ ЯЗЫКЕ. НИ ОДНОГО СЛОВА НА ДРУГИХ ЯЗЫКАХ.\n"
    "Запрещено использовать китайский, английский или любые другие языки.\n\n"
    "### РОЛЬ\n"
    "Ты — профессиональный образовательный ассистент {assistant}. "
    "Твоя цель — помогать студенту в освоении курса «{course}».\n\n"
    "### ПРАВИЛА ВЗАИМОДЕЙСТВИЯ\n"
    "1. ЯЗЫК: Всегда отвечай на русском языке. Это обязательно.\n"
    "2. СТИЛЬ: Будь лаконичным, доброжелательным и вдохновляющим.\n"
    "3. КОНТЕКСТ: Используй материалы курса. Если информации нет — скажи честно и предложи общие знания.\n"
    "4. ДЛЯ ОЗВУЧКИ: Избегай таблиц, сложных формул, markdown-разметки — говори простыми предложениями.\n"
    "5. ДЛИНА: Давай развёрнутые, но не перегруженные ответы — 2-4 абзаца.\n\n"
    "### НАВИГАЦИЯ (СИСТЕМНЫЕ КОМАНДЫ)\n"
    "{page_info}\n"
    "- Когда пользователь упоминает тему, ключевое слово или название курса (даже неточно), найди наиболее подходящий курс из списка и добавь тег в САМЫЙ КОНЕЦ ответа: [NAVIGATE:/courses/ID]\n"
    "- Примеры: 'базы данных' или 'бд' или 'sql' → [NAVIGATE:/courses/sql]. 'машинное обучение' или 'ml' или 'нейросети' → [NAVIGATE:/courses/ml].\n"
    "- Если просит вернуться на главную: [NAVIGATE:/]\n"
    "- Используй ТОЛЬКО теги из списка выше. Не придумывай другие пути.\n"
    "- Если ни один курс из списка не подходит по теме — скажи, что такого курса пока нет.\n\n"
    "### КОНТЕКСТ КУРСА\n"
    "{context}\n\n"
    "### ИСТОРИЯ ДИАЛОГА\n"
    "{history}\n"
    "Студент: {question}\n"
    "Ответ {assistant} (только на русском языке):"
)

_GLOBAL_PROMPT_TEMPLATE = (
    "### КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО\n"
    "ОТВЕЧАЙ ИСКЛЮЧИТЕЛЬНО НА РУССКОМ ЯЗЫКЕ. НИ ОДНОГО СЛОВА НА ДРУГИХ ЯЗЫКАХ.\n\n"
    "### РОЛЬ\n"
    "Ты — интеллектуальный гид образовательной платформы EduAI по имени {assistant}. "
    "Помогаешь пользователям ориентироваться на платформе и выбирать курсы.\n\n"
    "### ПРАВИЛА\n"
    "1. ЯЗЫК: Только русский. Без исключений.\n"
    "2. ПОМОЩЬ: Рассказывай о курсах платформы, помогай подобрать курс под интересы пользователя.\n"
    "3. СТИЛЬ: Дружелюбно, кратко, по существу. Без лишних вводных слов.\n"
    "4. ДЛЯ ОЗВУЧКИ: Говори простыми предложениями, без markdown и сложных символов.\n\n"
    "### НАВИГАЦИЯ\n"
    "{page_info}\n"
    "- Когда пользователь упоминает тему курса (даже неточно, по ключевым словам), найди подходящий курс и добавь тег в КОНЕЦ ответа: [NAVIGATE:/courses/ID]\n"
    "- Примеры: 'базы данных'/'бд'/'sql' → [NAVIGATE:/courses/sql]. 'питон'/'python' → [NAVIGATE:/courses/python]. 'веб'/'сайт'/'html' → [NAVIGATE:/courses/webdev]. 'ml'/'нейросети'/'машинное обучение' → [NAVIGATE:/courses/ml].\n"
    "- Используй ТОЛЬКО теги из списка. Не придумывай пути.\n\n"
    "### ИСТОРИЯ ДИАЛОГА\n"
    "{history}\n"
    "Пользователь: {question}\n"
    "Ответ {assistant} (только на русском языке):"
)


# ---------------------------------------------------------------------------
# Кешированные синглтоны
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
    name = course_name if course_name else settings.COURSE_NAME
    is_global = course_id == "default"
    template = _GLOBAL_PROMPT_TEMPLATE if is_global else _PROMPT_TEMPLATE

    page_info_parts = []
    available = page_context.get("available_courses", [])
    if available:
        courses_lines = "\n".join(
            f"  - {c.get('icon','')} {c.get('title', '')} ({c.get('description', '')}) → тег: [NAVIGATE:/courses/{c.get('id','')}]"
            for c in available
        )
        page_info_parts.append(f"Доступные курсы:\n{courses_lines}")
        page_info_parts.append("Главная страница → тег: [NAVIGATE:/]")

    page_info = ("\n".join(page_info_parts) + "\n") if page_info_parts else "(информация о курсах не передана)"

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
    if not docs:
        return "(материалы курса не найдены)"
    return "\n\n---\n\n".join(
        f"[{doc.metadata.get('source', 'Unknown')}]\n{doc.page_content}"
        for doc in docs
    )


def format_history(history: list[dict]) -> str:
    if not history:
        return ""
    lines = []
    for msg in history[-6:]:  # берём только последние 6 сообщений для экономии токенов
        role = "Студент" if msg.get("role") == "user" else settings.ASSISTANT_NAME
        content = msg.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) + "\n" if lines else ""


# ---------------------------------------------------------------------------
# Ingest — ИСПРАВЛЕН БАГ ДВОЙНОЙ ИНДЕКСАЦИИ
# ---------------------------------------------------------------------------

def ingest_documents(directory: str, course_id: str = "default") -> dict:
    """
    Загружает все поддерживаемые документы и индексирует их в ChromaDB.
    ИСПРАВЛЕНО: убрана двойная индексация (ранее документы добавлялись дважды).
    """
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

    LOADERS = {
        ".pdf":  lambda p: PyPDFLoader(p),
        ".docx": lambda p: Docx2txtLoader(p),
        ".txt":  lambda p: TextLoader(p, encoding="utf-8"),
        ".md":   lambda p: TextLoader(p, encoding="utf-8"),
    }

    store = get_vector_store(course_id)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

    total_chunks = 0
    total_docs = 0

    for file_path in Path(directory).rglob("*"):
        ext = file_path.suffix.lower()
        if ext not in LOADERS:
            continue
        try:
            # Пропускаем уже проиндексированные файлы
            existing = store._collection.get(where={"source": file_path.name})
            if existing and existing.get("ids") and len(existing["ids"]) > 0:
                logger.info(f"Пропуск (уже в индексе): {file_path.name}")
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
                logger.info(f"Проиндексировано: {file_path.name} → {len(chunks)} чанков (course={course_id})")

        except Exception as e:
            logger.error(f"Ошибка при загрузке {file_path.name}: {e}")

    if total_chunks == 0:
        return {"status": "warning", "message": "Новых документов не найдено", "chunks": 0, "documents": 0}

    logger.info(f"Итого: {total_chunks} чанков из {total_docs} страниц (course={course_id})")
    return {"status": "success", "documents": total_docs, "chunks": total_chunks}
