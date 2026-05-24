# Этап 1: Сборка Vue фронтенда
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Этап 2: Бэкенд FastAPI
FROM python:3.11-slim
WORKDIR /app

# Копируем зависимости
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бэкенда
COPY backend/ ./backend/

# Копируем собранный фронтенд в папку static бэкенда
COPY --from=frontend-builder /app/frontend/dist ./backend/static

# Настройка переменных окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend
ENV OLLAMA_BASE_URL=http://host.docker.internal:11434

# Порт
EXPOSE 8000

# Запуск
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
