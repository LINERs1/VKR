from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # =========================================================
    # LLM — меняй только эти две строки для смены модели
    # =========================================================
    LLM_PROVIDER: str = "gemini"        # "openai" | "gemini" | "ollama"
    LLM_MODEL: str = "gemini-2.5-flash" # чат и RAG — быстрая модель
    # Проверка ДЗ (пусто = как LLM_MODEL). Для ollama: qwen2.5:14b, mistral-nemo, …
    HOMEWORK_REVIEW_MODEL: str = ""

    # =========================================================
    # Облачные ключи API
    # =========================================================
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""  # только из .env / окружения, не коммить ключи
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # =========================================================
    # Embeddings
    # =========================================================
    EMBEDDING_PROVIDER: str = "gemini"  # "openai" | "gemini"
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"

    # SQLite (Docker: SQLITE_DATABASE_PATH=/data/app.db + volume)
    SQLITE_DATABASE_PATH: str = "./app.db"

    # =========================================================
    # ChromaDB
    # =========================================================
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION: str = "course_materials"

    # =========================================================
    # TTS — меняй TTS_PROVIDER для смены голосового движка
    # =========================================================
    TTS_PROVIDER: str = "edge"                      # "edge" | "elevenlabs" | "openai"
    TTS_VOICE: str = "ru-RU-SvetlanaNeural"         # edge-tts голос (ru-RU-DmitryNeural — мужской)
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "EXAVITQu4vr4xnSDxMaL"
    OPENAI_TTS_VOICE: str = "nova"                  # alloy | echo | fable | onyx | nova | shimmer
    SILERO_VOICE: str = "baya"                      # aidar | baya | kseniya | xenia | eugene
    SILERO_MODEL_PATH: str = "./models/silero_tts/v4_ru.pt"
    
    # F5-TTS (Cloning)
    F5_VOICE_REF: str = "./voices/reference.wav"    # Файл для клонирования голоса
    F5_VOICE_TEXT: str = ""                         # Текст, который произносится в reference.wav (для лучшего качества)

    # XTTS v2 (Better Cloning)
    XTTS_VOICE_REF: str = "./voices/reference.wav"  # Тот же файл для клонирования
    XTTS_MODEL_PATH: str = "./models/xtts_v2"       # Папка для модели XTTS

    # =========================================================
    # Ultravox (Cloud Voice AI)
    # =========================================================
    ULTRAVOX_API_KEY: str = ""          # API ключ с app.ultravox.ai
    ULTRAVOX_VOICE_ID: str = "d616943f-cf3e-44e3-9de6-336aaaec86c5"
    ULTRAVOX_VOICE_SPEED: float = 0.85  # Скорость речи TTS: 1.0 = норма, 0.85 ≈ на 15% медленнее (ElevenLabs: 0.7–1.2)
    ULTRAVOX_MODEL: str = "ultravox-v0.7"  # Модель для звонка — см. GET /api/ultravox/models
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"  # Публичный URL бэкенда (ngrok для разработки)

    # =========================================================
    # Assistant identity
    # =========================================================
    ASSISTANT_NAME: str = "Кортана"
    COURSE_NAME: str = "Образовательный курс"
    DEFAULT_COURSE_ID: str = "default"
    ASSISTANT_GREETING: str = "Привет! Я Кортана. Чем могу помочь?"

    # =========================================================
    # CORS — через запятую
    # =========================================================
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:8080"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
