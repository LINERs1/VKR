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
    "3. Слова «Голосовой помощник», «Эдуай», «ассистент» в начале сообщения — обращение к тебе, не имя пользователя.\n"
    "4. СТРОГОЕ ПРАВИЛО (САМОЕ ГЛАВНОЕ): Ты находишься ВНУТРИ конкретного курса «{course}». "
    "Отвечай и подсвечивай фрагменты ТОЛЬКО по материалам ЭТОГО курса. "
    "Если вопрос касается ДРУГОГО курса/языка/технологии (не текущего курса) — НЕ подсвечивай, НЕ переходи туда, НЕ ставь теги навигации. "
    "Кратко скажи, что этот вопрос вне рамок текущего курса, и предложи уточнить по теме «{course}».\n"
    "5. Отвечай лаконично: 2–4 абзаца. Без лишней воды.\n"
    "6. ВАЖНО: ответ не должен превышать 400 слов. Если тема требует большего — предложи задать уточняющий вопрос.\n\n"
    "{role_capabilities}\n"
    "### НАВИГАЦИЯ\n"
    "{page_info}\n\n"
    "ПРАВИЛА навигации:\n"
    "- Журнал, Профиль, Главная, Домашние задания, Аналитика, Мастерская — тег [NAVIGATE:/путь] сразу при явной просьбе.\n"
    "    Главная: [NAVIGATE:/] или [NAVIGATE:]. Примеры: «домой», «на главную» → [NAVIGATE:/].\n"
    "- ПЕРЕХОД НА ДРУГОЙ КУРС ЗАПРЕЩЁН. Никогда не ставь тег [NAVIGATE:/courses/...] и не предлагай перейти на другой курс внутри текущего курса. "
    "Если пользователь хочет другой курс — пусть сам вернётся на главную (можешь подсказать: «Вернитесь на главную и выберите нужный курс»).\n"
    "- ПРАВИЛО ВЫБОРА КУРСА: Если пользователь ищет курс, и найдено БОЛЬШЕ 3 вариантов, верни команду [SHOW_COURSES:его_запрос] вместо [NAVIGATE:...]. Это откроет визуальное окно выбора.\n"
    "- Только ОДИН тег навигации на весь ответ.\n"
    "- Не придумывай пути — используй только те, что в списке выше.\n\n"
    "### ПОДСВЕТКА ФРАГМЕНТА\n"
    "Подсветка работает ТОЛЬКО по материалам текущего курса «{course}».\n"
    "Когда отвечаешь на вопрос по текущему курсу и в источниках ниже есть релевантный фрагмент — "
    "выбери ОДНУ дословную цитату (до 8 слов) из {context} и пометь её тегом [HIGHLIGHT:дословная цитата] в КОНЦЕ ответа.\n"
    "ПРАВИЛА подсветки:\n"
    "- Цитата должна быть ДОСЛОВНОЙ из материалов текущего курса — фронт ищет точное совпадение по тексту страницы.\n"
    "- Бери заголовок, ключевое определение или первое предложение релевантного абзаца/кода.\n"
    "- НИКОГДА не подсвечивай фрагменты из других курсов или из ответа общими словами.\n"
    "- Если фрагмента нет в материалах текущего курса — тег НЕ ставь.\n"
    "- Только ОДИН тег [HIGHLIGHT:...] на весь ответ.\n\n"
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
    "3. Слова «Голосовой помощник», «Эдуай», «ассистент» в начале сообщения — обращение к тебе, не имя пользователя.\n"
    "4. Рассказывай о курсах, помогай выбрать подходящий.\n"
    "5. ВАЖНО: ответ не должен превышать 400 слов. Если тема требует большего — предложи задать уточняющий вопрос.\n\n"
    "{role_capabilities}\n"
    "### НАВИГАЦИЯ\n"
    "{page_info}\n\n"
    "ПРАВИЛА навигации:\n"
    "- Журнал, Профиль, Главная, Домашние задания, Аналитика, Мастерская — тег [NAVIGATE:/путь] сразу при явной просьбе.\n"
    "    Главная: [NAVIGATE:/] или [NAVIGATE:]. Примеры: «домой», «на главную» → [NAVIGATE:/].\n"
    "    Примеры: «открой профиль» → [NAVIGATE:/profile], «покажи журнал» → [NAVIGATE:/journal].\n"
    "- Переход на КУРС — два шага:\n"
    "    Шаг 1: назови полное название, спроси «Перейти на страницу курса «…»?» — БЕЗ тега.\n"
    "    Шаг 2: после «да/давай/ок» — «Открываю курс «…»» и тег [NAVIGATE:/courses/id] в конце.\n"
    "- ПРАВИЛО ВЫБОРА КУРСА: Если пользователь ищет курс, и найдено БОЛЬШЕ 3 вариантов, верни команду [SHOW_COURSES:его_запрос] вместо [NAVIGATE:...]. Это откроет визуальное окно выбора.\n"
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

def get_retriever(course_id: str = "default", k: int = 6):
    return get_vector_store(course_id).as_retriever(search_kwargs={"k": k})


def parse_lesson_id_from_source(source: str, course_id: str | None = None) -> int | None:
    """lesson_{course_id}_{id}, lesson_v2_{id}_..., lesson_{id}."""
    if not source or not source.startswith("lesson_"):
        return None
    parts = source.split("_")
    if len(parts) >= 3 and parts[1] == "v2" and parts[2].isdigit():
        return int(parts[2])
    if course_id:
        prefix = f"lesson_{course_id}_"
        if source.startswith(prefix):
            tail = source[len(prefix) :].split("_")[0]
            if tail.isdigit():
                return int(tail)
    if len(parts) >= 3 and parts[-1].isdigit():
        return int(parts[-1])
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return None


def _collection_doc_count(course_id: str) -> int:
    try:
        coll = getattr(get_vector_store(course_id), "_collection", None)
        if coll is not None:
            return int(coll.count())
    except Exception as e:
        logger.debug("collection count failed for %s: %s", course_id, e)
    return 0


async def retrieve_course_docs(course_id: str, query: str, k: int = 6) -> list:
    """Семантический поиск с fallback-запросами для коротких/голосовых фраз."""
    if _collection_doc_count(course_id) == 0:
        logger.warning("ChromaDB пуста для course_id=%s — нужен webhook / sync_all_to_ai.py", course_id)
        return []

    retriever = get_retriever(course_id, k=k)
    docs = await retriever.ainvoke(query)
    if docs:
        return docs

    q = (query or "").lower()
    fallbacks: list[str] = []
    if any(w in q for w in ("for", "in", "цикл", "loop", "перебор", "итерац")):
        fallbacks.extend(["цикл for in Python", "for item in", "цикл for перебирает"])
    if "функц" in q or "def " in q:
        fallbacks.append("определение функции def")
    fallbacks.append(query.split()[0] if query.split() else query)

    seen: set[str] = set()
    for fb in fallbacks:
        fb = (fb or "").strip()
        if not fb or fb in seen:
            continue
        seen.add(fb)
        docs = await retriever.ainvoke(fb)
        if docs:
            logger.info("RAG fallback hit for course=%s query=%r -> %r", course_id, query, fb)
            return docs
    return []


def get_chain(course_name: str = None, course_id: str = "default", page_context: dict = {}, current_user = None):
    name = course_name if course_name else settings.COURSE_NAME
    is_global = course_id == "default"
    template = _GLOBAL_PROMPT_TEMPLATE if is_global else _PROMPT_TEMPLATE

    page_info_parts = []
    
    curr_path = page_context.get('current_path', '/')
    curr_page = page_context.get('current_page', 'Неизвестно')
    loc_lines = [f"- Страница: {curr_page}", f"- URL: {curr_path}"]
    breadcrumbs = page_context.get("breadcrumbs")
    if breadcrumbs:
        from app.services.navigation_service import build_breadcrumbs_text
        crumb_text = build_breadcrumbs_text(breadcrumbs)
        if crumb_text:
            loc_lines.append(f"- Путь: {crumb_text}")
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
    
    # Используем граф из БД, если он передан, иначе откатываемся к старому списку
    db_nav_routes = page_context.get("db_nav_routes")
    if db_nav_routes:
        page_info_parts.append(build_navigation_prompt(db_nav_routes, voice=False))
    else:
        page_info_parts.append("Списка маршрутов нет, так как отсутствует подключение к БД в данном контексте.")
        
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

def format_docs(docs: List[Document], db=None) -> str:
    if not docs:
        return "(материалы курса не найдены)"
        
    formatted_docs = []
    for doc in docs:
        source = doc.metadata.get('source', 'Unknown')
        course_id = doc.metadata.get('course_id')
        
        real_path = ""
        if source.startswith("lesson_") and course_id:
            lesson_id = parse_lesson_id_from_source(source, course_id)
            if lesson_id is not None:
                real_path = f"/courses/{course_id}?lesson={lesson_id}"
        
        path_hint = ""
        if real_path:
            path_hint = f", Маршрут: {real_path}"
            
        formatted_docs.append(f"[Источник: {source}{path_hint}]\n{doc.page_content}")
        
    return "\n\n---\n\n".join(formatted_docs)


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
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)

    total_chunks = 0
    total_docs = 0

    for lesson in course.lessons:
        source_name = f"lesson_v2_{lesson.id}_{lesson.title}.txt"
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


def ingest_text(
    text: str,
    source_name: str,
    course_id: str,
    extra_metadata: dict | None = None,
) -> dict:
    """Индексирует произвольный текст в ChromaDB для указанного курса.
    
    Используется webhook-обработчиком при получении нового урока/контента от платформы.
    """
    from langchain_core.documents import Document

    if not text or not text.strip():
        return {"status": "skipped", "reason": "empty text"}

    store = get_vector_store(course_id)
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)

    if _indexed_source_exists(store, source_name):
        logger.info("ingest_text: re-indexing existing source: %s", source_name)
        delete_document(source_name, course_id)

    metadata = {"source": source_name, "course_id": course_id}
    if extra_metadata:
        metadata.update(extra_metadata)

    doc = Document(page_content=text.strip(), metadata=metadata)
    chunks = splitter.split_documents([doc])
    if not chunks:
        return {"status": "skipped", "reason": "no chunks after split"}

    store.add_documents(chunks)
    _clear_vector_store_cache()
    logger.info("ingest_text: indexed %d chunks for source=%s course=%s", len(chunks), source_name, course_id)
    return {"status": "ok", "chunks": len(chunks)}


def delete_document(source_name: str, course_id: str) -> dict:
    """Удаляет документ из ChromaDB по имени источника."""
    try:
        store = get_vector_store(course_id)
        coll = getattr(store, "_collection", None)
        if coll is None:
            return {"status": "error", "reason": "no collection"}
        existing = coll.get(where={"source": source_name})
        ids = existing.get("ids") if existing else []
        if ids:
            coll.delete(ids=ids)
            _clear_vector_store_cache()
            logger.info("delete_document: removed %d chunks for source=%s", len(ids), source_name)
            return {"status": "ok", "deleted": len(ids)}
        return {"status": "not_found"}
    except Exception as e:
        logger.error("delete_document error: %s", e)
        return {"status": "error", "reason": str(e)}
