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
from app.utils.navigation_prompt import build_navigation_prompt

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
    "4. ДОМАШНИЕ ЗАДАНИЯ (ВАЖНО!):\n"
    "   - Если пользователь **Студент (student)** и просит помочь с ДЗ: **НИКОГДА НЕ ПИШИ РЕШЕНИЕ ИЛИ КОД**. Задавай наводящие вопросы (сократический метод), давай подсказки.\n"
    "   - Если пользователь **Преподаватель (teacher)** и просит проверить ДЗ: Проведи **ПОЛНЫЙ АНАЛИЗ** кода и ответа студента на основе методички. Укажи на ошибки и оцени. **КРИТИЧЕСКИ ВАЖНО:** Если ты находишь ошибку в коде или тексте ученика, обязательно выделяй этот ошибочный фрагмент красным цветом, оборачивая его в тег <span style='color: #ef4444; font-weight: bold;'>ошибочный код/текст</span>, чтобы преподаватель сразу это увидел.\n"
    "5. ДЛЯ ОЗВУЧКИ: Избегай таблиц, сложных формул, markdown-разметки — говори простыми предложениями.\n"
    "6. ДЛИНА: Давай развёрнутые, но не перегруженные ответы — 2-4 абзаца.\n"
    "7. РАЗГОВОР И ВОПРОСЫ: Если студент здоровается, спрашивает «как дела?» или ведёт короткую вежливую беседу — ответь **своими словами**, кратко и по-человечески.\n"
    "**Запрещено** отвечать одной фразой, которая только повторяет, зеркалит или перефразирует вопрос студента без нового смысла.\n"
    "   Если в сообщении в начале есть «Кортана», «Эдуай», «ассистент» — это **код вызова**, не имя студента.\n\n"
    "### ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ\n"
    "{user_info}\n\n"
    "### НАВИГАЦИЯ И КОНТЕКСТ\n"
    "{page_info}\n"
    "- Если студент просит открыть Журнал, Профиль или Главную страницу — сразу ставь тег [NAVIGATE:/...] в конце ответа.\n"
    "- Если студент просит **перейти на другой курс**, навигация происходит в два этапа:\n"
    "    1. Предложи курс и спроси подтверждение (БЕЗ ТЕГА).\n"
    "    2. При согласии — ставь тег [NAVIGATE:/courses/...].\n"
    "- Не придумывай свои пути для тегов.\n\n"
    "### КОНТЕКСТ КУРСА\n"
    "{context}\n\n"
    "### ИСТОРИЯ ДИАЛОГА\n"
    "{history}\n"
    "Студент: {question}\n"
    "Ответ {assistant} (только на русском языке):"
)

_GLOBAL_PROMPT_TEMPLATE = (
    "### КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО\n"
    "ОТВЕЧАЙ ИСКЛЮЧИТЕЛЬНО НА РУСКОМ ЯЗЫКЕ. НИ ОДНОГО СЛОВА НА ДРУГИХ ЯЗЫКАХ.\n\n"
    "ОТВЕЧАЙ ИСКЛЮЧИТЕЛЬНО НА РУССКОМ ЯЗЫКЕ. НИ ОДНОГО СЛОВА НА ДРУГИХ ЯЗЫКАХ.\n\n"
    "### РОЛЬ\n"
    "Ты — интеллектуальный гид образовательной платформы EduAI по имени {assistant}. "
    "Помогаешь пользователям ориентироваться на платформе и выбирать курсы.\n\n"
    "### ПРАВИЛА\n"
    "1. ЯЗЫК: Только русский. Без исключений.\n"
    "2. ПОМОЩЬ: Рассказывай о курсах платформы, помогай подобрать курс под интересы пользователя.\n"
    "   Слова «Кортана», «Эдуай», «ассистент» в **начале** сообщения — это **код вызова ассистента**, а не имя пользователя. **Не** обращайся к человеку «Кортана» и не строй ответ так, будто это его имя.\n"
    "7. ПЕРЕХОД НА СТРАНИЦЫ (НАВИГАЦИЯ):\n"
    "   - Если пользователь явно просит открыть Журнал, Профиль, Главную или Домашние задания (например: «открой профиль», «давай посмотрим журнал», «домой») — просто вставь соответствующий тег [NAVIGATE:/...] в конец ответа. Подтверждение НЕ ТРЕБУЕТСЯ.\n"
    "   - Если пользователь просит перевести его на **КОНКРЕТНЫЙ КУРС** (например: «хочу изучать питон»), то навигация на курс требует **двух шагов**:\n"
    "       Шаг А: Назови полное название курса и спроси: «Перевести на страницу курса «…»?» (ТЕГ НЕ СТАВИТЬ!). Не говори «на этот курс» без названия.\n"
    "       Шаг Б: После «да»/«давай»/«ок» — «Открываю курс «…»» и тег [NAVIGATE:/courses/ID] в конце.\n"
    "   - Вставляй только ОДИН тег навигации на весь ответ.\n\n"
    "### НАВИГАЦИЯ И КОНТЕКСТ\n"
    "{page_info}\n"
    "- Не придумывай другие пути и id, используй только те, что перечислены выше.\n\n"
    "### ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ\n"
    "{user_info}\n\n"
    "### КОНТЕКСТ (подсказка системы, не дословно пользователю)\n"
    "{context}\n\n"
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


def get_chain(course_name: str = None, course_id: str = "default", page_context: dict = {}, current_user = None):
    name = course_name if course_name else settings.COURSE_NAME
    is_global = course_id == "default"
    template = _GLOBAL_PROMPT_TEMPLATE if is_global else _PROMPT_TEMPLATE

    page_info_parts = []
    
    curr_path = page_context.get('current_path', '/')
    curr_page = page_context.get('current_page', 'Неизвестно')
    page_info_parts.append(f"ТЕКУЩЕЕ МЕСТОПОЛОЖЕНИЕ ПОЛЬЗОВАТЕЛЯ:\n- Страница: {curr_page}\n- URL: {curr_path}\n")
    
    page_content = page_context.get('page_content', '')
    if page_content:
        page_info_parts.append(f"СОДЕРЖИМОЕ ЭКРАНА (что видит пользователь прямо сейчас):\n\"\"\"\n{page_content}\n\"\"\"\n(Опирайся на эти данные, если пользователь просит проанализировать страницу, графики или оценки).\n")
    else:
        page_info_parts.append("(Учитывай это при ответах. Если пользователь спрашивает 'где я?', скажи ему это).\n")
    
    available = page_context.get("available_courses", [])
    page_info_parts.append(build_navigation_prompt(available, voice=False))
    page_info = "\n".join(page_info_parts) + "\n"

    user_info = "Пользователь не авторизован (Гость)."
    if current_user:
        role_ru = "Ученик" if current_user.role == "student" else "Преподаватель" if current_user.role == "teacher" else current_user.role
        user_info = f"Имя: {current_user.username}\nРоль: {role_ru} ({current_user.role})"

    prompt = PromptTemplate(
        template=template,
        input_variables=["context", "question", "history"],
        partial_variables={
            "assistant": settings.ASSISTANT_NAME,
            "course": name,
            "page_info": page_info,
            "user_info": user_info,
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
            existing = store._collection.get(where={"source": file_path.name})
            if existing and existing.get("ids") and len(existing["ids"]) > 0:
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
            existing = store._collection.get(where={"source": source_name})
            if existing and existing.get("ids") and len(existing["ids"]) > 0:
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
    return {"status": "success", "documents": total_docs, "chunks": total_chunks}
