# ==========================================
# Этап 1: Сборка Vue 3 фронтенда
# ==========================================
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

# Копируем файлы фронтенда
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .

# Собираем фронтенд (он будет лежать в /app/frontend/dist)
# При сборке указываем, что API бэкенда будет доступно по относительному пути /api
ENV VITE_API_BASE_URL=/api
RUN npm run build

# ==========================================
# Этап 2: Сборка Python FastAPI бэкенда
# ==========================================
FROM python:3.12-slim
WORKDIR /app

# Устанавливаем системные зависимости (нужны для сборки некоторых python-пакетов)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости бэкенда
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь бэкенд (папки app, data, models, voices и т.д.)
COPY backend/app ./app
COPY backend/data ./data
# Если папки models и voices нужны для работы (TTS/RAG), раскомментируйте:
# COPY backend/models ./models
# COPY backend/voices ./voices
# COPY backend/scripts ./scripts

# Копируем собранный фронтенд из первого этапа в папку static (FastAPI сам их раздаст)
COPY --from=frontend-builder /app/frontend/dist ./static

# ==========================================
# Настройки окружения (Конфигурация для проверяющего)
# ==========================================
# Указываем, что используем локальные модели без сторонних API
ENV USE_LOCAL_LLM=True
ENV LLM_PROVIDER=ollama
ENV LLM_MODEL=qwen2.5
ENV EMBEDDING_PROVIDER=ollama
ENV EMBEDDING_MODEL=nomic-embed-text

# Важно: Docker контейнер должен стучаться в Ollama, установленную на самом компьютере (хосте).
# host.docker.internal пробрасывает порт на ПК пользователя.
ENV OLLAMA_BASE_URL=http://host.docker.internal:11434

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Открываем порт 8000
EXPOSE 8000

# Запускаем Uvicorn (FastAPI)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
