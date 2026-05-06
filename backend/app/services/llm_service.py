from langchain_core.language_models.chat_models import BaseChatModel
from app.config import settings


def get_llm() -> BaseChatModel:
    """
    Returns the configured LLM.
    To switch providers — change LLM_PROVIDER in .env:
      ollama  → local Ollama (llama3.2, mistral, etc.)
      openai  → OpenAI API (gpt-4o-mini, gpt-4o, etc.)
    """
    if settings.LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.LLM_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.3,
        )

    if settings.LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3,
            streaming=True,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: '{settings.LLM_PROVIDER}'. "
        "Supported values: 'ollama', 'openai'"
    )
