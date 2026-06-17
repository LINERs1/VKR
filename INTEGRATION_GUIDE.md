# Руководство по интеграции AI-сервиса в образовательную платформу

> Документ для программиста, который подключает AI-сервис (`ai_service/`) к новой образовательной платформе (LMS) со своей БД курсов и уроков.
>
> Прочитай **целиком** перед началом — шаги завязаны друг на друга. Минимальный набор для запуска: **§4 → §5 → §7 → §8 → §10**.

---

## 0. Кратко: что есть и что куда передаётся

AI-сервис **не хранит полные курсы**. Он держит три локальные сущности и наполняет их из платформы:

```
┌──────────────────────────── ПЛАТФОРМА (LMS) ────────────────────────────┐
│  БД: courses, lessons, users, homeworks                                 │
│  REST: GET /api/courses  →  [{id, title, lessons:[{id,title,content}]}] │
└───────────────────────────────────┬─────────────────────────────────────┘
            GET (pull, при старте)   │   POST/DELETE (webhook, при CRUD)
                                    ▼
┌──────────────────────────── AI-СЕРВИС (порт 8000) ───────────────────────┐
│  SQLite (app.db):                                                       │
│    course_refs / lesson_refs   ← зеркала (id + title)                   │
│    nav_nodes / nav_edges       ← граф навигации                         │
│    node_access_rules           ← роли доступа                           │
│    chat_messages, assistant_metrics                                     │
│  ChromaDB (chroma_db/):       ← векторный индекс текстов уроков         │
│    коллекция course_materials_<course_id>                               │
└─────────────────────────────────────────────────────────────────────────┘
```

| Сущность | Где | Зачем | Кто наполняет |
|---|---|---|---|
| `CourseRef`/`LessonRef` | SQLite | генерация путей `/courses/{id}` | seed / webhook / auto-pull |
| `NavNode`/`NavEdge`/`NodeAccessRule` | SQLite | валидация `[NAVIGATE:...]`, «куда можно идти» | seed / webhook / auto-pull |
| Векторный индекс | ChromaDB | RAG-поиск по материалам курса | webhook / auto-pull / `ingest_text` |

**Порт/URL по умолчанию:**
- AI-сервис: **`http://localhost:8000`**
- Платформа: **`http://localhost:8001`** (значение `PLATFORM_SERVICE_URL` в AI-сервисе)

---

## 1. Структура репозитория

```
Diplom/
├── ai_service/                 ← ТОТ САМЫЙ AI-сервис (порт 8000)
│   ├── app/
│   │   ├── main.py            ← FastAPI-приложение, роутинг, lifespan (seed + sync)
│   │   ├── config.py          ← Settings: URL, ключи, модели
│   │   ├── database.py        ← SQLAlchemy engine/SessionLocal
│   │   ├── api/
│   │   │   ├── chat.py        ← /api/chat, /api/chat/stream, /api/chat/voice
│   │   │   ├── ultravox.py    ← /api/ultravox/* — голосовые сессии
│   │   │   ├── navigation.py  ← /api/navigation/* — резолв маршрутов
│   │   │   ├── widget.py      ← /api/widget/config
│   │   │   ├── documents.py   ← /api/* — индексация файлов
│   │   │   ├── stt.py         ← /api/stt — Speech-to-Text
│   │   │   ├── analytics.py   ← /api/analytics/*
│   │   │   ├── homework_check.py ← /api/homework/* — ИИ-проверка ДЗ
│   │   │   └── webhooks.py    ← /webhook/* — ПРИЁМНИКИ ОТ ПЛАТФОРМЫ
│   │   ├── services/
│   │   │   ├── rag_service.py ← промпты, retriever, get_chain, ingest_*
│   │   │   ├── navigation_service.py ← резолв/фаззи-поиск курсов
│   │   │   ├── platform_client.py ← GET /api/courses платформы
│   │   │   ├── platform_sync.py ← сверка графа + auto-pull
│   │   │   ├── auth_service.py ← JWT (get_current_user / _optional)
│   │   │   ├── platform_auth.py ← verify_service_token (для webhook)
│   │   │   ├── ultravox_tools.py ← голосовые tools (navigatePage, openLesson…)
│   │   │   ├── tts_service.py, chat_history_service.py, metrics_service.py
│   │   ├── models/
│   │   │   ├── navigation.py  ← NavNode, NavEdge, NodeAccessRule
│   │   │   ├── mirror.py      ← CourseRef, LessonRef
│   │   │   ├── chat_message.py, assistant_metric.py
│   │   ├── utils/
│   │   │   ├── seed.py        ← начальный граф + зеркала
│   │   │   ├── navigation_prompt.py ← построение текста маршрутов для промпта
│   │   │   ├── role_capabilities.py
│   │   ├── .env               ← КЛЮЧИ И URL (см. §2)
│   ├── app.db                 ← SQLite (можно удалить для чистого старта)
│   └── chroma_db/             ← векторная БД (можно удалить)
│
├── platform_service/           ← НОВАЯ платформа (порт 8001) — куда интегрируем
└── backend/                    ← старый монолит (референс, не используем)
```

---

## 2. Переменные окружения (`ai_service/.env`)

```env
# === LLM / Embeddings ===
LLM_PROVIDER=gemini                       # openai | gemini | ollama
LLM_MODEL=gemini-2.5-flash
EMBEDDING_PROVIDER=gemini                 # openai | gemini
EMBEDDING_MODEL=models/gemini-embedding-001
GEMINI_API_KEY=...                        # ОБЯЗАТЕЛЬНО для gemini-провайдера
OPENAI_API_KEY=...                        # если LLM/EMBEDDING_PROVIDER=openai

# === Интеграция с платформой ===
PLATFORM_SERVICE_URL=http://localhost:8001  # URL НОВОЙ платформы (GET /api/courses)
SERVICE_API_KEY=<общий секрет>              # для webhook-авторизации платформы

# === Голосовой режим (Ultravox) ===
ULTRAVOX_API_KEY=...                      # app.ultravox.ai
ULTRAVOX_VOICE_ID=...
BACKEND_PUBLIC_URL=http://localhost:8000  # публичный URL AI-сервиса (для Ultravox callbacks)

# === TTS ===
TTS_PROVIDER=edge                         # edge | elevenlabs | openai

# === JWT (общий с платформой!) ===
# Задаётся через JWT_SECRET_KEY (см. §8). По умолчанию захардкожен — ЗАМЕНИ.

# === Идентичность ассистента ===
ASSISTANT_NAME=Голосовой помощник
COURSE_NAME=Образовательный курс
DEFAULT_COURSE_ID=default
```

> Полный список — `ai_service/app/config.py`. Все переменные читаются из `.env` (кодировка UTF-8).

**На стороне платформы** (`platform_service/backend/.env`) зеркально:
```env
AI_SERVICE_URL=http://localhost:8000
AI_SERVICE_KEY=<тот же SERVICE_API_KEY>
```

---

## 3. Запуск сервисов (локально)

```bash
# Терминал 1 — Платформа
cd platform_service/backend
.venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Терминал 2 — AI-сервис
cd ai_service
.venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Или一键: `run_services.bat` (открывает два окна cmd).

В Docker: `docker-compose up` (сервисы `ai_service` + `platform_backend` + nginx:80).

---

## 4. ЗАДАЧА №1: эндпоинт `GET /api/courses` на платформе

> 🔴 **Без этого не работает ничего.** Это единственный обязательный pull-канал.

AI-сервис при старте и при каждом запросе навигации идёт на `GET {PLATFORM_SERVICE_URL}/api/courses` (`platform_client.py`) и ждёт **JSON-массив курсов** в формате:

```json
[
  {
    "id": "python-100-days-ru",
    "title": "Python за 100 дней",
    "description": "Полный курс",
    "icon": "🐍",
    "lessons": [
      {
        "id": 1,
        "title": "Введение в Python",
        "content": "Полный текст урока для RAG-индексации..."
      },
      { "id": 2, "title": "Переменные", "content": "..." }
    ]
  }
]
```

**Обязательные поля и типы (ВАЖНО):**

| Поле | Тип | Примечание |
|---|---|---|
| `id` | **string** | slug курса = URL `/courses/{id}` на фронте. Строка, не число! |
| `title` | string | название |
| `lessons[].id` | **integer** | число (в `LessonRef` колонка `Integer`) |
| `lessons[].title` | string | |
| `lessons[].content` | string | **полный текст урока** → пойдёт в ChromaDB для RAG |

Необязательные (но желательные): `description`, `icon`, `color`, `lessons_count`.

**Реализуй на платформе** ручку (референс — `backend/app/api/courses.py`):
```python
@router.get("/courses")
async def get_courses(db: Session = Depends(get_db)):
    return [{
        "id": c.id, "title": c.title, "description": c.description, "icon": c.icon,
        "lessons": [{"id": l.id, "title": l.title, "content": l.content}
                    for l in c.lessons]
    } for c in db.query(Course).all()]
```

### ⚠️ Авторизация эндпоинта
Сейчас `fetch_platform_courses` идёт **без токена**. Если `/api/courses` требует auth — либо открой его публично, либо доработай `platform_client.py`:
```python
headers={"Authorization": f"Bearer {settings.SERVICE_API_KEY}"}
```

### Проверка
```bash
curl http://localhost:8001/api/courses | python -m json.tool
```
Должен вернуть массив с `content` в уроках. Если `content` пустой — RAG не найдёт материалы.

---

## 5. ЗАДАЧА №2: авто-наполнение при старте (pull)

Если §4 сделан правильно, **граф и ChromaDB заполнятся автоматически** при запуске AI-сервиса. Логика:

1. `main.py:lifespan` → `seed_database(db)` — создаёт базовые узлы (`/`, `/profile`, `/journal`, `/homeworks`, `/analytics`, `ACTION:CHECK_HW`, `ACTION:GET_HINT`), если БД пуста (`utils/seed.py:142`).
2. → `check_course_sync(db)` (`services/platform_sync.py:16`) — сравнивает NavNode-курсы с тем, что отдала платформа.
3. Недостающие курсы тянет `auto_pull_missing_courses` (`platform_sync.py:64`):
   - создаёт `CourseRef` + `LessonRef`;
   - создаёт `NavNode` для курса (`/courses/{id}`) и каждого урока (`/courses/{id}?lesson={N}`);
   - прокладывает рёбра: `Главная → Курс → Урок` и `Урок → ACTION:CHECK_HW/GET_HINT` (`can_execute`);
   - индексирует текст уроков в ChromaDB (по коллекции `course_materials_{course_id}`).

### Чистый старт (если БД не пустая или кривая)
```bash
# Останови AI-сервис, затем:
del ai_service\app.db
rmdir /s /q ai_service\chroma_db
# Запусти заново — seed + auto-pull отстроят всё с нуля.
```

> ⚠️ `seed_*` и `check_course_sync` **идемпотентны**, но **не обновляют** существующие записи. После изменения курсов на платформе либо удаляй `app.db`+`chroma_db`, либо используй webhook'и (§6).

### Что проверить в логах AI-сервиса при старте
```
✅ Авто-загрузка завершена: добавлено курсов: N, чанков текста: M
```
Если видишь `⚠️ Nav sync: платформа недоступна или курсов нет` — `GET /api/courses` не ответил (не тот порт / нужен токен / платформа не запущена).

---

## 6. ЗАДАЧА №3 (опционально, но рекомендуется): webhook'и для CRUD в реальном времени

Чтобы новые/изменённые курсы попадали в AI-сервис **без перезапуска**, платформа должна слать webhook'и при создании/обновлении/удалении. Все 5 ручек — в `ai_service/app/api/webhooks.py`, защищены заголовком:

```
Authorization: Bearer {SERVICE_API_KEY}
```

| Метод | Путь | Тело (JSON) | Эффект в AI-сервисе |
|---|---|---|---|
| **POST** | `/webhook/course` | `{id, title}` | `CourseRef` + `NavNode /courses/{id}` + ребро от Главной |
| **DELETE** | `/webhook/course/{id}` | — | удаление зеркала, NavNode, чанков ChromaDB |
| **POST** | `/webhook/lesson` | `{id, course_id, title, content}` | `LessonRef` + `NavNode ?lesson=` + индекс в ChromaDB |
| **DELETE** | `/webhook/lesson/{id}` | — | удаление урока + его чанков |
| **POST** | `/webhook/content` | `{id, course_id, title, content, source_type}` | индекс методички/справочника (без NavNode). `source_type`: `methodology` \| `reference` |

### Пример вызова с платформы (FastAPI)
```python
import httpx, os
AI_URL = os.getenv("AI_SERVICE_URL")     # http://localhost:8000
AI_KEY = os.getenv("AI_SERVICE_KEY")

async def notify_ai_lesson_created(lesson):
    await httpx.AsyncClient().post(
        f"{AI_URL}/webhook/lesson",
        json={
            "id": lesson.id,
            "course_id": lesson.course_id,
            "title": lesson.title,
            "content": lesson.content,      # ОБЯЗАТЕЛЬНО полный текст
        },
        headers={"Authorization": f"Bearer {AI_KEY}"},
        timeout=10,
    )
```

Вызывай это в сигналах (`post_save` / `post_delete`) или сервисном слое платформы после `commit`. На старте достаточно авто-pull (§5); webhook'и — для актуальности в рантайме.

---

## 7. ЗАДАЧА №4: авторизация пользователей (JWT) — КРИТИЧНО

AI-сервис идентифицирует пользователя по JWT в заголовке `Authorization: Bearer <token>` (`services/auth_service.py`).

### Контракт токена
```python
payload = {
    "sub": "username",       # логин (ОБЯЗАТЕЛЬНО — без него 401)
    "role": "student",       # student | teacher | admin
    "id": 42,                # числовой id пользователя
    "settings_json": "...",  # опционально
    "exp": <unix>            # срок действия
}
```

### Секрет
```python
# auth_service.py:12
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key-for-diplom-ai-123")
ALGORITHM = "HS256"
```

🔴 **Оба сервиса (платформа + AI) должны подписывать JWT одним и тем же `JWT_SECRET_KEY`.** Задай его в `.env` обоих сервисов:
```env
JWT_SECRET_KEY=<длинная случайная строка>
```

### Если у новой платформы другая схема auth
- Другой claim (например `user_id` вместо `id`, или `username` в другом поле) — доработай `get_current_user` в `auth_service.py` (строки 49–53).
- Другой алгоритм / не JWT — придётся адаптировать. Это частая точка боли при интеграции.

### Где какой эндпоинт какой auth требует
| Поведение | Зависимость |
|---|---|
| Гость разрешён (виджет без логина) | `get_current_user_optional` → `None`, если токена нет |
| Требуется вход | `get_current_user` → 401 без/с плохим токеном |
| Только преподаватель/админ | `get_current_teacher` |

Чат и голосовой режим используют `_optional` — работают и для гостей (но история не сохраняется).

---

## 8. ЗАДАЧА №5: фронтенд — монтаж виджета и page_context

Виджет чата — `frontend/src/components/GlobalAssistant.vue` (или `ChatWidget.vue` для упрощённого текстового). Он обращается к AI-сервису по относительным путям `/api/...`, значит нужен **прокси**.

### 8.1. Прокси в `vite.config.js` нового фронта
```js
export default defineConfig({
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },  // AI-сервис
      // если ручки платформы тоже под /api — раздели префиксы
    }
  }
})
```
В проде — то же делает nginx (см. `docker-compose.yml`, сервис `nginx`).

### 8.2. Контракт `page_context` (что виджет шлёт в `/api/chat/stream`)
Формируется в `GlobalAssistant.vue:294` (`pageContext`). При встраивании виджета в новый фронт обеспечь передачу:

```js
{
  current_path: "/courses/python-100-days-ru?lesson=1",
  current_page: "Курс",
  current_course_id: "python-100-days-ru",
  current_course_name: "Python за 100 дней",
  breadcrumbs: [{label:"Главная", path:"/"}, {label:"Python", path:"/courses/python-100-days-ru"}],
  lesson_id: "1",                    // строка
  lesson_title: "Введение в Python",
  lesson_index: 1,                   // 1-based
  total_lessons: 10,
  available_courses: [               // для [SHOW_COURSES] и валидации NAVIGATE
    {id:"python-100-days-ru", title:"Python", icon:"🐍", description:"..."}
  ],
}
```

Плюс `page_content` — текст текущей страницы (виджет берёт сам через `getPageText()`, читая DOM-селекторы `.course-content .content-wrapper` / `.course-content` / `main`).

### 8.3. Если DOM новой платформы отличается
`getPageText()` в `GlobalAssistant.vue:105` читает текст урока из селекторов:
```js
document.querySelector('.course-content .content-wrapper') ||
document.querySelector('.course-content') ||
document.querySelector('main')
```
Если уроки рендерятся в другом контейнере — добавь свой селектор в начало списка. От этого зависит, корректно ли модель «видит» страницу и подсветка работает.

---

## 9. Навигационный граф: что, как и где править

Граф = направленный: `NavNode` (узлы) + `NavEdge` (рёбра `navigates_to` / `can_execute`) + `NodeAccessRule` (роли).

### Структура
```
/  (Главная, depth=1)
├── /profile, /journal, /homeworks, /analytics, /homeworks/workshop  (статика, depth=1-2)
├── /courses/{id}  (depth=2)
│   └── /courses/{id}?lesson={N}  (depth=3)
│       ├── can_execute → ACTION:CHECK_HW
│       └── can_execute → ACTION:GET_HINT
```

### Что меняется под новую платформу
1. **URL статических страниц** — в `utils/seed.py:108-113` (`add_node("/profile", ...)` и т.д.). Если на новой платформе `/profile` → `/me`, поправь тут. Иначе модель будет предлагать несуществующие пути.
2. **Роли** — `seed.py` и `ultravox_tools.py` используют `student`/`teacher`/`admin`. Если у вас другие — замени глобально.
3. **Кастомные страницы** — можно добавить через REST без правки кода:
   ```bash
   curl -X POST http://localhost:8000/api/navigation/custom-nodes \
     -H "Content-Type: application/json" \
     -d '{"identifier":"/workshop","title":"Мастерская","allowed_roles":["teacher"]}'
   ```
4. **Базовые ACTION-узлы** (`ACTION:CHECK_HW`, `ACTION:GET_HINT`) — нужны для рёбер `can_execute` от уроков. Если функции проверки ДЗ нет — рёбра безвредны (просто не вызовутся).

### Проверка графа
```bash
curl http://localhost:8000/api/navigation/dynamic-nodes   # курсы/уроки/actions
curl http://localhost:8000/api/navigation/custom-nodes    # статические страницы
curl http://localhost:8000/api/navigation/sync-status     # сверка с платформой
```

---

## 10. Чек-лист запуска (минимальный)

Прогони по порядку:

```bash
# 1. Платформа отдаёт курсы с content
curl http://localhost:8001/api/courses | python -m json.tool
#   → массив, у каждого курса lessons[].content не пустой

# 2. AI-сервис жив
curl http://localhost:8000/api/health
#   → {"status":"ok", ...}

# 3. Чистый старт (если нужно перестроить индекс)
del ai_service\app.db
rmdir /s /q ai_service\chroma_db
# перезапусти AI-сервис, в логах: "✅ Авто-загрузка завершена..."

# 4. Граф навигации заполнен
curl http://localhost:8000/api/navigation/dynamic-nodes
#   → есть узлы /courses/{id} и /courses/{id}?lesson={N}

# 5. RAG работает (текстовый чат)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"о чём курс Python?\",\"course_id\":\"python-100-days-ru\"}"
#   → answer с реальным содержанием, не "материалы курса не найдены"

# 6. (с авторизацией) История сохраняется
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"тест\",\"course_id\":\"python-100-days-ru\",\"page_context\":{...}}"
#   → SSE-стрим, после которого в chat_messages появится запись
```

Если на шаге 4 пусто → авто-pull не сработал (проверь `PLATFORM_SERVICE_URL`, формат `/api/courses`, логи).
Если на шаге 5 «материалы курса не найдены» → `content` не проиндексирован (ChromaDB пуста или `content` пустой в ответе платформы).

---

## 11. Типичные проблемы

| Симптом | Причина | Решение |
|---|---|---|
| `⚠️ Nav sync: платформа недоступна` | AI не достучался до платформы | проверь `PLATFORM_SERVICE_URL`, что платформа на 8001 запущена |
| Граф не заполняется, но `/api/courses` работает | БД не пустая → seed/sync пропустили | удали `app.db` + `chroma_db`, перезапусти |
| RAG отвечает «материалы не найдены» | ChromaDB пуста для курса | проверь `content` в `/api/courses`; перезапусти для переиндексации |
| Чат работает, но 401 / история не сохраняется | JWT-несовпадение | один `JWT_SECRET_KEY` в обоих сервисах (§7) |
| Виджет шлёт запросы не туда | нет прокси `/api` | настрой `vite.config.js` (§8.1) |
| Навигация «открой профиль» ведёт на 404 | URL в графе не совпадает с фронтом | поправь `seed.py` под реальные пути (§9) |
| `Lesson.id` принимается как строка | в `/api/courses` id как строка | сделай `id` числом (Integer) |
| Подсветка не работает | DOM-селектор другой | поправь `getPageText()` (§8.3) |
| Авто-pull дублирует узлы | запускали несколько раз с кривой БД | удали `app.db`, запусти один раз |

---

## 12. Ссылки на ключевые файлы (что читать дальше)

| Файл | Что внутри |
|---|---|
| `ai_service/app/main.py` | роутинг всех endpoint'ов, lifespan (seed+sync при старте) |
| `ai_service/app/config.py` | все переменные окружения |
| `ai_service/app/services/platform_client.py` | GET `/api/courses` с платформы |
| `ai_service/app/services/platform_sync.py` | сверка графа + `auto_pull_missing_courses` |
| `ai_service/app/api/webhooks.py` | 5 webhook-приёмников (контракт с платформой) |
| `ai_service/app/utils/seed.py` | базовый граф + зеркала (править под новую платформу) |
| `ai_service/app/models/navigation.py` | NavNode/NavEdge/NodeAccessRule |
| `ai_service/app/models/mirror.py` | CourseRef/LessonRef |
| `ai_service/app/services/rag_service.py` | промпты, retriever, `get_chain`, `ingest_text` |
| `ai_service/app/services/navigation_service.py` | резолв путей, фаззи-поиск курсов, алиасы |
| `ai_service/app/services/auth_service.py` | JWT, `get_current_user(_optional)` |
| `ai_service/app/services/ultravox_tools.py` | голосовые tools (navigatePage, openLesson, RAG) |
| `ai_service/app/api/navigation.py` | REST навигации: resolve, validate, custom-nodes |
| `frontend/src/components/GlobalAssistant.vue` | виджет: `pageContext`, `getPageText`, SSE-обработка |

---

## 13. Краткий порядок внедрения

```
0. .env обоих сервисов: PLATFORM_SERVICE_URL, SERVICE_API_KEY, JWT_SECRET_KEY, ключи LLM
1. На платформе: GET /api/courses → [{id,title,lessons:[{id,title,content}]}]
2. Запусти платформу → запусти AI-сервис → авто-pull наполнит граф + ChromaDB
3. Проверь /api/navigation/dynamic-nodes и текстовый чат (§10)
4. JWT: общий секрет, фронт шлёт Authorization: Bearer
5. Фронт: прокси /api → AI-сервис, монтаж виджета с page_context
6. (позже) webhook'и при CRUD курса/урока
7. (под новую платформу) поправь seed.py (URL стат.страниц, роли) и getPageText() (DOM)
```

**Минимум для «функции работают»**: шаги 0, 1, 2, 4, 5.
```
