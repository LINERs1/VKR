# Руководство разработчика платформы — интеграция с EduAI

Пошаговая инструкция: **у вас уже есть LMS с курсами и уроками**, **ИИ-сервис стартует с пустой базой**. Что сделать, чтобы заработали голос, RAG, навигация и домашние задания.

> Справочник JSON-эндпоинтов: [README_API.md](./README_API.md)  
> Машиночитаемый контракт: `GET http://localhost:8000/api/embeddable/contract`

---

## 0. Две системы — кто за что отвечает

```
┌──────────────────────────────┐         ┌──────────────────────────────┐
│  ВАША ПЛАТФОРМА (LMS)        │         │  ИИ-СЕРВИС (EduAI)           │
│  platform.db                 │         │  app.db + chroma_db/         │
├──────────────────────────────┤         ├──────────────────────────────┤
│ • Пользователи, роли, JWT    │         │ • Зеркало курсов (id+title)  │
│ • Полные тексты уроков       │ webhook │ • Граф навигации (NavNode)   │
│ • Домашние задания, оценки   │ ──────► │ • Векторный индекс (ChromaDB) │
│ • Source of truth            │         │ • LLM, Ultravox, RAG         │
└──────────────────────────────┘         └──────────────────────────────┘
         ▲                                           │
         │         JWT (виджет) + SERVICE_API_KEY    │
         └───────────────────────────────────────────┘
```

| Данные | Где хранятся | Как попадают в ИИ |
|--------|--------------|-------------------|
| Курс (id, название) | Платформа | `POST /webhook/course` |
| Урок (текст лекции) | Платформа | `POST /webhook/lesson` (+ индекс в ChromaDB) |
| PDF/DOCX методички | Платформа | `POST /webhook/content` |
| ДЗ, код студента, оценки | **Только платформа** | ИИ получает **по запросу** при проверке/подсказке |
| Пользователи | Платформа (+ копия в ai для JWT) | Общий `JWT_SECRET_KEY` |

**Важно:** ИИ **не подтягивает** уроки сам при старте. Платформа **отправляет webhooks** (или один раз — скрипт синхронизации).

---

## 1. Первый запуск инфраструктуры

### 1.1. Запустить сервисы

```bash
docker compose up --build
```

| Сервис | URL | Назначение |
|--------|-----|------------|
| Frontend (виджет) | http://localhost | UI + прокси `/api/*` |
| Платформа | http://localhost:8001 | Курсы, auth, ДЗ |
| ИИ | http://localhost:8000 | Голос, RAG, навигация |

### 1.2. Обязательные переменные окружения

**Одинаковые в обоих `.env`:**

```env
# platform_service/backend/.env  и  ai_service/.env
SERVICE_API_KEY=ваш-секрет-для-webhooks
JWT_SECRET_KEY=ваш-секрет-для-jwt
```

**Платформа:**

```env
AI_SERVICE_URL=http://ai_service:8000    # в Docker
# AI_SERVICE_URL=http://localhost:8000   # локальная разработка
```

**ИИ:**

```env
PLATFORM_SERVICE_URL=http://platform_backend:8001
ULTRAVOX_API_KEY=...          # для голоса
GEMINI_API_KEY=...            # или Ollama — см. ai_service/.env
```

### 1.3. LLM (если не облако)

```bash
ollama pull qwen2.5
ollama pull nomic-embed-text
```

---

## 2. Заполнить платформу данными

ИИ **не видит** ваши курсы, пока платформа их не отдаст.

### 2.1. Вариант A — демо-seed (уже в проекте)

При старте `platform_backend` автоматически создаёт курсы `algorithms`, `ml`, `webdev`, `sql` с уроками и текстами.

Проверка:

```bash
curl http://localhost:8001/api/courses
```

### 2.2. Вариант B — свой курс через API

```http
POST /api/courses
Authorization: Bearer <admin_jwt>
Content-Type: application/json

{
  "id": "my-course",
  "title": "Мой курс",
  "description": "Описание",
  "icon": "📘",
  "color": "#3366ff",
  "tags": "python, начинающий",
  "duration": "10 часов",
  "instructor": "Иван Иванов"
}
```

При создании курса платформа **автоматически** шлёт webhook `POST /webhook/course` в ИИ.

### 2.3. Уроки

Уроки лежат в таблице `lessons` (поле `content` — текст для RAG).  
Добавляйте через свой CRUD или seed/migration.

> **Сейчас в коде:** webhook на **создание курса** уже есть; на **создание/редактирование урока** — нужно вызывать webhook вручную или добавить в ваш API (см. п. 3.2).

---

## 3. Заполнить ИИ-сервис (синхронизация)

После того как на **платформе** есть курсы и уроки, нужно **один раз** (и далее при каждом изменении) передать их в ИИ.

### 3.1. Что происходит при каждом webhook

| Webhook | Что пишется в ИИ |
|---------|------------------|
| `POST /webhook/course` | `CourseRef`, узел навигации `/courses/{id}` |
| `POST /webhook/lesson` | `LessonRef`, узел `/courses/{id}?lesson={id}`, **текст в ChromaDB** |
| `POST /webhook/content` | Методичка/справочник в ChromaDB (без NavNode) |
| `DELETE /webhook/course/{id}` | Удаление зеркала и индекса |
| `DELETE /webhook/lesson/{id}` | Удаление урока из графа и ChromaDB |

**Без webhook урока** RAG не найдёт материал, голос не сможет ответить по теме курса.

### 3.2. Первичная синхронизация (все курсы разом)

Если платформа уже была заполнена до подключения ИИ:

```bash
cd platform_service/backend
python scripts/sync_all_to_ai.py
```

Скрипт для каждого курса и урока вызывает webhooks с `X-Service-Token`.

**Пример ручного вызова (Python на стороне платформы):**

```python
from app.utils.ai_client import send_webhook

# Курс
send_webhook("/webhook/course", {"id": "algorithms", "title": "Алгоритмы"})

# Урок (content обязателен для RAG!)
send_webhook("/webhook/lesson", {
    "id": 1,
    "course_id": "algorithms",
    "title": "Введение в Python",
    "content": "Python — язык программирования...\n\nprint('Hello')",
})
```

**Пример curl:**

```bash
curl -X POST http://localhost:8000/webhook/lesson \
  -H "Content-Type: application/json" \
  -H "X-Service-Token: ваш-секрет" \
  -d '{"id":1,"course_id":"algorithms","title":"Урок 1","content":"Текст урока..."}'
```

### 3.3. Что добавить в код платформы (рекомендуется)

В каждом месте, где вы **создаёте/обновляете/удаляете** сущность:

| Событие на платформе | Вызов |
|----------------------|-------|
| Создан/обновлён курс | `send_webhook("/webhook/course", {...})` |
| Создан/обновлён урок | `send_webhook("/webhook/lesson", {...})` |
| Удалён курс | `ai_delete("/webhook/course/{id}")` |
| Удалён урок | `ai_delete("/webhook/lesson/{id}")` |
| Загружен PDF/DOCX | `send_webhook("/webhook/content", {...})` |

Готовый клиент: `platform_service/backend/app/utils/ai_client.py`.

### 3.4. Проверить, что синхронизация прошла

```bash
# ИИ видит те же курсы, что и платформа?
curl http://localhost:8000/api/navigation/sync-status

# Пример ответа:
# {"platform_reachable": true, "platform_course_count": 4, "course_ids": ["algorithms", "ml", ...]}
```

В логах `ai_service` при старте: `Nav sync: N курсов совпадают` или предупреждение о расхождениях.

**Типичная ошибка:** в NavNode ИИ есть `python-100-days-ru`, на платформе курса нет → голос ведёт на 404. Решение: импортировать курс на платформу **или** не синхронизировать лишнее.

---

## 4. Настройка платформы для всех функций ИИ

После синхронизации контента настройте **интеграцию на стороне LMS**.

### 4.1. Общее для всех функций

| # | Что сделать | Зачем |
|---|-------------|-------|
| 1 | Один `JWT_SECRET_KEY` на платформе и в `ai_service` | Виджет ходит в оба сервиса с одним токеном |
| 2 | `AI_SERVICE_URL` указывает на ИИ | Webhooks и проверка ДЗ |
| 3 | `SERVICE_API_KEY` одинаковый | Защита webhooks и `/api/homework/check` |
| 4 | Встроить виджет (или свой UI) с прокси `/api/ultravox`, `/api/navigation` → :8000 | Голос и RAG |
| 5 | При логине отдавать JWT с полями `sub` (user id), `role` (`student`/`teacher`) | Allowlist инструментов |

### 4.2. Матрица функций

| Функция | Что нужно в ИИ (после sync) | Что прописать на платформе |
|---------|----------------------------|----------------------------|
| **Голосовой ассистент** | Ultravox key, ChromaDB с уроками | Виджет: `POST /api/ultravox/call` + JWT; передавать `available_courses`, `page_content`, `permissions` |
| **Контекст экрана** | — | Виджет: `POST /api/ultravox/context` при смене страницы |
| **RAG / ответы по курсу** | Webhooks уроков с `content` | `course_id` в запросах; курсы в `navigation/resolve` |
| **Навигация голосом** | NavNode для `/`, `/journal`, `/courses/{id}` | Виджет: перед `router.push` → `POST /api/navigation/resolve` с `courses[]` |
| **Подсветка фрагмента** | RAG-чанки с текстом урока | Страница курса обрабатывает `highlight_text`; см. README_API §12 |
| **Текстовый чат** | ChromaDB | `POST /api/chat` + JWT |
| **Подсказки по ДЗ** | LLM | `POST /api/homework/assignments/{id}/hint` — **только через платформу** (лимиты, 403) |
| **ИИ-проверка ДЗ** | LLM | Платформа: `POST /api/homework/check` на ИИ с `X-Service-Token`; UI: `POST .../ai-review` |
| **Журнал / сводка** | — | `GET /api/homework/journal/summary` на **платформе** |
| **Методички PDF** | Webhook `/webhook/content` | Загрузка через `/api/materials` (уже шлёт webhook) |
| **Audit / аналитика** | Таблица `audit_logs` | `GET /api/audit/events`, `GET /api/analytics/summary` на ИИ |

### 4.3. Виджет: минимальный payload при старте голоса

```javascript
await fetch('/api/ultravox/call', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  },
  body: JSON.stringify({
    session_id: crypto.randomUUID(),
    course_id: currentCourseId,
    course_name: currentCourseName,
    current_path: window.location.pathname,
    page_content: document.body.innerText.slice(0, 1500),
    permissions: ['navigate', 'rag', 'homework_hint', 'notifications'], // для student
    available_courses: coursesFromYourApi,  // GET /api/courses
  }),
})
// Ответ: { joinUrl, sessionId, granted_permissions }
```

Список `permissions` по ролям — см. [README_API.md §1](./README_API.md).

### 4.4. Домашние задания — цепочка вызовов

```
Студент просит подсказку (голос)
  → tool getHomeworkHint (виджет)
  → POST /api/homework/assignments/{id}/hint  (платформа, JWT student)
  → LLM на платформе + пост-фильтр
  → { "hint": "..." }

Преподаватель просит проверку (голос, confirm=true)
  → tool reviewHomework (виджет)
  → POST /api/homework/assignments/{id}/ai-review  (платформа, JWT teacher)
  → POST /api/homework/check  (платформа → ИИ, X-Service-Token)
  → { teacher_feedback, suggested_grade, error_fragments }
  → платформа сохраняет в assignment.ai_review_json
```

На платформе должны быть: модели `Homework`, `HomeworkAssignment`, эндпоинты hint и ai-review (уже есть в `platform_service`).

### 4.5. Пользователи для теста

После seed платформы:

| Логин | Пароль | Роль |
|-------|--------|------|
| `st` | `st` | student |
| `te` | `te` | teacher |
| `admin` | `admin` | admin |

JWT получить: `POST /api/auth/login`.

---

## 5. Чеклист «всё работает»

Выполняйте по порядку:

- [ ] `docker compose up`, оба health: `:8001/api/health`, `:8000/api/health`
- [ ] `GET /api/courses` на платформе — есть курсы с уроками
- [ ] Запущен `python scripts/sync_all_to_ai.py` (или webhooks при каждом CRUD)
- [ ] `GET /api/navigation/sync-status` — `platform_reachable: true`, id курсов совпадают
- [ ] Логин student/teacher, виджет открывается
- [ ] Голос: «открой курс algorithms» — переход без 404
- [ ] Голос: вопрос по теме урока — RAG находит ответ (если урок был в webhook с `content`)
- [ ] Студент на странице ДЗ — подсказка приходит, без готового кода
- [ ] Преподаватель — «проверь ДЗ» → подтверждение → результат на экране
- [ ] `GET /api/audit/events` (teacher) — видны `voice_call_started`, `homework_check`

---

## 6. Частые проблемы

| Симптом | Причина | Решение |
|---------|---------|---------|
| ИИ «знает» курс, страница 404 | Курс в NavNode, нет на платформе | Синхронизировать только существующие курсы; проверить sync-status |
| RAG: «материалы не найдены» | Уроки не отправлены в ИИ | `sync_all_to_ai.py` или webhook lesson с `content` |
| Webhook 401 | Нет/неверный `SERVICE_API_KEY` | Одинаковый ключ в обоих `.env` |
| Ultravox не подключается | Нет `ULTRAVOX_API_KEY` | Ключ в `ai_service/.env` |
| Подсказка 403 | Не student / не своя работа | Проверить JWT и assignment |
| Проверка ДЗ 503 | ИИ недоступен / LLM | Проверить Ollama/Gemini, логи ai_service |
| JWT invalid на ИИ | Разные секреты | Один `JWT_SECRET_KEY` |

---

## 7. Порядок действий (кратко)

1. **Поднять** platform + ai + frontend, прописать `.env`.
2. **Наполнить платформу** (seed, API, импорт) — курсы, уроки с текстом, ДЗ.
3. **Синхронизировать ИИ** — webhooks или `scripts/sync_all_to_ai.py`.
4. **Проверить** `navigation/sync-status` и RAG на одном уроке.
5. **Подключить виджет** — JWT, `available_courses`, context, permissions.
6. **Включить webhooks** в CRUD платформы на будущее (курс/урок/материал).
7. **Проверить** голос, навигацию, подсказку, проверку ДЗ по чеклисту §5.

---

## 8. Связанные файлы в репозитории

| Файл | Назначение |
|------|------------|
| `platform_service/backend/app/utils/ai_client.py` | HTTP-клиент к ИИ (webhooks) |
| `platform_service/backend/app/services/ai_homework_client.py` | Проверка ДЗ через ИИ |
| `platform_service/backend/scripts/sync_all_to_ai.py` | Первичная синхронизация |
| `ai_service/app/api/webhooks.py` | Приёмник webhooks |
| `frontend/src/components/GlobalAssistant.vue` | Референсный виджет |
| `README_API.md` | JSON запросы/ответы всех API |
