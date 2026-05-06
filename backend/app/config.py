from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # --- LLM ---
    LLM_PROVIDER: str = "ollama"        # "ollama" | "openai"
    LLM_MODEL: str = "llama3.2"         # "gpt-4o-mini" for openai

    # --- Ollama ---
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # --- OpenAI (optional) ---
    OPENAI_API_KEY: str = ""

    # --- Embeddings ---
    EMBEDDING_PROVIDER: str = "ollama"  # "ollama" | "openai"
    EMBEDDING_MODEL: str = "nomic-embed-text"

    # --- ChromaDB ---
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION: str = "course_materials"

    # --- TTS ElevenLabs (optional) ---
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "EXAVITQu4vr4xnSDxMaL"

    # --- Assistant identity ---
    ASSISTANT_NAME: str = "EduAI"
    COURSE_NAME: str = "Образовательный курс"

    # --- CORS ---
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
