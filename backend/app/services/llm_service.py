from langchain_core.language_models.chat_models import BaseChatModel
from app.config import settings


def get_llm() -> BaseChatModel:
    """
    Returns the configured LLM.
    To switch providers — change LLM_PROVIDER in .env:
      openai  → OpenAI API (gpt-4o-mini, gpt-4o, etc.)
      gemini  → Google Gemini API (gemini-1.5-flash, gemini-1.5-pro, etc.)
    """

    if settings.LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3,
            streaming=True,
        )

    if settings.LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.3,
        )

    if settings.LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=0.3,
            client_kwargs={
                "headers": {"ngrok-skip-browser-warning": "true"},
                "timeout": 300.0  # Увеличиваем таймаут до 5 минут
            },
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: '{settings.LLM_PROVIDER}'. "
        "Supported values: 'openai', 'gemini'"
    )
