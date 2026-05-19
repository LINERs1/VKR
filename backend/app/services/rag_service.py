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
from app.utils.navigation_prompt import build_navigation_routes_list
from app.utils.role_capabilities import build_role_capabilities_prompt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Промпты — ВАЖНО: явное требование отвечать ТОЛЬКО на русском языке
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = (
    "### ЯЗЫК\n"
    "ВСЕГДА отвечай ТОЛЬКО на русском языке. Ни одного слова на других языках.\n\n"
    "### КТО ТЫ\n"
    "Ты — {assistant}, умный и дружелюбный ассистент образовательной платформы EduAI.\n"
    "Текущий курс: «{course}».\n"
    "Пользователь: {user_info}\n\n"
    "### КАК СЕБЯ ВЕСТИ\n"
    "1. Отвечай живо и по-человечески. Не копируй вопрос, не зеркаль его.\n"
    "2. Если спрашивают «как дела», «привет» — отвечай кратко и тепло, своими словами.\n"
    "3. Слова «Кортана», «Эдуай», «ассистент» в начале сообщения — обращение к тебе, не имя пользователя.\n"
    "4. Используй материалы курса. Если информации нет — скажи честно и помоги общими знаниями.\n"
    "5. Отвечай лаконично: 2–4 абзаца. Без лишней воды.\n\n"
    "{role_capabilities}\n"
    "### НАВИГАЦИЯ\n"
    "{page_info}\n\n"
    "ПРАВИЛА навигации:\n"
    "- Журнал, Профиль, Главная, Домашние задания — тег [NAVIGATE:/путь] сразу при явной просьбе.\n"
    "    Главная: [NAVIGATE:/] или [NAVIGATE:]. Примеры: «домой», «на главную» → [NAVIGATE:/].\n"
    "- Переход на ДРУГОЙ КУРС — два шага:\n"
    "    Шаг 1: назови полное название курса, спроси «Перейти на страницу курса «…»?» — БЕЗ тега.\n"
    "    Шаг 2: после «да/давай/ок» — «Открываю курс «…»» и тег [NAVIGATE:/courses/id] в конце.\n"
    "- Только ОДИН тег навигации на весь ответ.\n"
    "- Не придумывай пути — используй только те, что в списке выше.\n\n"
    "### МАТЕРИАЛЫ КУРСА\n"
    "{context}\n\n"
    "### ИСТОРИЯ\n"
    "{history}\n"
    "Пользователь: {question}\n"
    "{assistant}:"
)

_GLOBAL_PROMPT_TEMPLATE = (
    "### ЯЗЫК\n"
    "ВСЕГДА отвечай ТОЛЬКО на русском языке. Ни одного слова на других языках.\n\n"
    "### КТО ТЫ\n"
    "Ты — {assistant}, умный и дружелюбный гид образовательной платформы EduAI.\n"
    "Помогаешь пользователям ориентироваться на платформе и выбирать курсы.\n"
    "Пользователь: {user_info}\n\n"
    "### КАК СЕБЯ ВЕСТИ\n"
    "1. Отвечай живо, тепло, по-человечески. Не зеркаль вопрос.\n"
    "2. На приветствие и «как дела» — отвечай кратко своими словами.\n"
    "3. Слова «Кортана», «Эдуай», «ассистент» в начале сообщения — обращение к тебе, не имя пользователя.\n"
    "4. Рассказывай о курсах, помогай выбрать подходящий.\n\n"
    "{role_capabilities}\n"
    "### НАВИГАЦИЯ\n"
    "{page_info}\n\n"
    "ПРАВИЛА навигации:\n"
    "- Журнал, Профиль, Главная, Домашние задания — тег [NAVIGATE:/путь] сразу при явной просьбе.\n"
    "    Главная: [NAVIGATE:/] или [NAVIGATE:]. Примеры: «домой», «на главную» → [NAVIGATE:/].\n"
    "    Примеры: «открой профиль» → [NAVIGATE:/profile], «покажи журнал» → [NAVIGATE:/journal].\n"
    "- Переход на КУРС — два шага:\n"
    "    Шаг 1: назови полное название, спроси «Перейти на страницу курса «…»?» — БЕЗ тега.\n"
    "    Шаг 2: после «да/давай/ок» — «Открываю курс «…»» и тег [NAVIGATE:/courses/id] в конце.\n"
    "- Только ОДИН тег навигации на весь ответ.\n"
    "- Не придумывай пути — только из списка выше.\n\n"
    "### КОНТЕКСТ\n"
    "{context}\n\n"
    "### ИСТОРИЯ\n"
    "{history}\n"
    "Пользователь: {question}\n"
    "{assistant}:"
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
        # trust_env=False — иначе httpx берёт системный прокси Windows и Ollama отвечает 503
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


def get_chain(course_name: str = None, course_id: str = "default", page_context: dict = {}, current_user = None):
    name = course_name if course_name else settings.COURSE_NAME
    is_global = course_id == "default"
    template = _GLOBAL_PROMPT_TEMPLATE if is_global else _PROMPT_TEMPLATE

    page_info_parts = []
    
    curr_path = page_context.get('current_path', '/')
    curr_page = page_context.get('current_page', 'Неизвестно')
    loc_lines = [f"- Страница: {curr_page}", f"- URL: {curr_path}"]
    lesson_title = page_context.get('lesson_title')
    if lesson_title:
        lesson_idx = page_context.get('lesson_index')
        total = page_context.get('total_lessons')
        lesson_id = page_context.get('lesson_id', '')
        pos = f" ({lesson_idx} из {total})" if lesson_idx and total else ""
        loc_lines.append(f"- Текущий урок: «{lesson_title}»{pos}, lesson_id: {lesson_id}")
    page_info_parts.append("ТЕКУЩЕЕ МЕСТОПОЛОЖЕНИЕ ПОЛЬЗОВАТЕЛЯ:\n" + "\n".join(loc_lines) + "\n")
    
    page_content = page_context.get('page_content', '')
    if page_content:
        page_info_parts.append(f"СОДЕРЖИМОЕ ЭКРАНА (что видит пользователь прямо сейчас):\n\"\"\"\n{page_content}\n\"\"\"\n(Опирайся на эти данные, если пользователь просит проанализировать страницу, графики или оценки).\n")
    else:
        page_info_parts.append("(Учитывай это при ответах. Если пользователь спрашивает 'где я?', скажи ему это).\n")
    
    available = page_context.get("available_courses", [])
    user_role = current_user.role if current_user else None
    page_info_parts.append(build_navigation_routes_list(available, role=user_role))
    weak_block = (page_context or {}).get("weak_topics_prompt", "")
    if weak_block:
        page_info_parts.append(weak_block)
    page_info = "\n".join(page_info_parts) + "\n"

    user_info = "Пользователь не авторизован (Гость)."
    if current_user:
        role_ru = "Ученик" if current_user.role == "student" else "Преподаватель" if current_user.role == "teacher" else current_user.role
        user_info = f"Имя: {current_user.username}\nРоль: {role_ru} ({current_user.role})"

    role_capabilities = build_role_capabilities_prompt(user_role)

    prompt = PromptTemplate(
        template=template,
        input_variables=["context", "question", "history"],
        partial_variables={
            "assistant": settings.ASSISTANT_NAME,
            "course": name,
            "page_info": page_info,
            "user_info": user_info,
            "role_capabilities": role_capabilities,
        },
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
# Ingest
# ---------------------------------------------------------------------------

def _indexed_source_exists(store: Chroma, source_name: str) -> bool:
    """Проверка наличия документа в индексе без приватного API, где возможно."""
    try:
        if hasattr(store, "get"):
            existing = store.get(where={"source": source_name})
            ids = existing.get("ids") if isinstance(existing, dict) else None
            if ids and len(ids) > 0:
                return True
    except Exception as e:
        logger.debug("store.get failed for %s: %s", source_name, e)
    try:
        coll = getattr(store, "_collection", None)
        if coll is not None:
            existing = coll.get(where={"source": source_name})
            if existing and existing.get("ids") and len(existing["ids"]) > 0:
                return True
    except Exception as e:
        logger.debug("collection.get failed for %s: %s", source_name, e)
    return False


def _clear_vector_store_cache() -> None:
    get_vector_store.cache_clear()


def ingest_documents(directory: str, course_id: str = "default") -> dict:
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
    from pathlib import Path

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
            logger.error(f"Ошибка при загрузке {file_path.name}: {e}")

    if total_chunks == 0:
        return {"status": "warning", "message": "Новых документов не найдено", "chunks": 0, "documents": 0}

    _clear_vector_store_cache()
    return {"status": "success", "documents": total_docs, "chunks": total_chunks}


def ingest_documents_from_db(course, db) -> dict:
    """
    Загружает тексты уроков курса из SQLite и индексирует их в ChromaDB.
    """
    from langchain_core.documents import Document

    store = get_vector_store(course.id)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

    total_chunks = 0
    total_docs = 0

    for lesson in course.lessons:
        source_name = f"lesson_{lesson.id}_{lesson.title}.txt"
        try:
            # Пропускаем уже проиндексированные файлы
            if _indexed_source_exists(store, source_name):
                logger.info(f"Пропуск (уже в индексе): {source_name}")
                continue

            # Создаем документ из текста лекции
            doc = Document(
                page_content=lesson.content,
                metadata={"source": source_name, "course_id": course.id}
            )
            docs = [doc]

            chunks = text_splitter.split_documents(docs)
            if chunks:
                store.add_documents(chunks)
                total_chunks += len(chunks)
                total_docs += len(docs)
                logger.info(f"Проиндексировано: {source_name} → {len(chunks)} чанков (course={course.id})")

        except Exception as e:
            logger.error(f"Ошибка при загрузке {source_name}: {e}")

    if total_chunks == 0:
        return {"status": "warning", "message": "Новых документов не найдено", "chunks": 0, "documents": 0}

    logger.info(f"Итого: {total_chunks} чанков из {total_docs} лекций (course={course.id})")
    if total_chunks > 0:
        _clear_vector_store_cache()
    return {"status": "success", "documents": total_docs, "chunks": total_chunks}
