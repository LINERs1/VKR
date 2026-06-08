import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings

logger = logging.getLogger(__name__)


def get_llm(model: str | None = None) -> BaseChatModel:
    """
    Returns the configured LLM.
    To switch providers — change LLM_PROVIDER in .env:
      openai  → OpenAI API (gpt-4o-mini, gpt-4o, etc.)
      gemini  → Google Gemini API (gemini-1.5-flash, gemini-1.5-pro, etc.)
    """
    model_name = (model or settings.LLM_MODEL).strip()

    if settings.LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3,
            streaming=True,
        )

    if settings.LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.3,
        )

    if settings.LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        ollama_client = {"trust_env": False, "timeout": 300.0}
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=model_name,
            temperature=0.2 if model_name != settings.LLM_MODEL else 0.3,
            client_kwargs=ollama_client,
            sync_client_kwargs=ollama_client,
            async_client_kwargs=ollama_client,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: '{settings.LLM_PROVIDER}'. "
        "Supported values: 'openai', 'gemini', 'ollama'"
    )


def get_homework_llm() -> BaseChatModel:
    """Более тяжёлая модель только для ИИ-проверки ДЗ (см. HOMEWORK_REVIEW_MODEL)."""
    model_name = (settings.HOMEWORK_REVIEW_MODEL or settings.LLM_MODEL).strip()
    logger.info("Homework review: %s / %s", settings.LLM_PROVIDER, model_name)
    return get_llm(model_name)
