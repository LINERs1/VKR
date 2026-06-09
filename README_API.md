# EduAI — API интеграции embeddable голосового ассистента

> **Пошаговое руководство** (пустая БД ИИ → синхронизация → настройка платформы): **[DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)**

Документ для разработчиков **образовательной платформы (LMS)**, которая встраивает виджет ИИ.

- **ИИ-сервис** (`ai_service`, порт `8000`) — голос, RAG, навигация, проверка ДЗ.
- **Платформа** (`platform_service`, порт `8001`) — пользователи, курсы, ДЗ, source of truth.

> Машиночитаемый контракт: `GET http://localhost:8000/api/embeddable/contract`

---

## 1. Модель безопасности (Security model)

### Принцип

**LLM и Ultravox не доверяем.** Финальное решение всегда на стороне платформы и виджета:

1. ИИ **предлагает** действие (tool call).
2. Виджет **проверяет** роль, страницу, `permissions[]`.
3. Платформа **выполняет** REST-запрос с JWT и возвращает 403 при нарушении прав.

### Два уровня авторизации

| Уровень | Заголовок | Кто использует | Для чего |
|---------|-----------|----------------|----------|
| Пользователь | `Authorization: Bearer <JWT>` | Браузер / виджет | Голос, чат, навигация |
| Сервис | `X-Service-Token: <SERVICE_API_KEY>` | Бэкенд платформы | Webhooks, проверка ДЗ |

JWT подписан общим секретом (настраивается в `.env` обоих сервисов).

### Permissions (права)

Платформа может передать явный список `permissions[]`. ИИ выдаёт только инструменты, разрешённые **и ролью, и permissions**.

| Permission | Инструменты Ultravox |
|------------|---------------------|
| `navigate` | `navigatePage`, `openLesson`, `openAdjacentLesson`, `getPageContext` |
| `rag` | `queryKnowledgeBase` |
| `homework_hint` | `getHomeworkHint`, `getHomeworkReminders` |
| `homework_review` | `reviewHomework` |
| `homework_mass_review` | `reviewAllHomeworks` |
| `journal_summary` | `getTeacherSummary` |
| `homework_form` | `fillHomeworkForm` |
| `notifications` | `getNotifications`, `clearNotifications` |

**По умолчанию для ролей:**

- `student` → `navigate`, `rag`, `homework_hint`, `notifications`
- `teacher` / `admin` → все permissions

---

## 2. Схема интеграции

```
┌─────────────┐     JWT      ┌──────────────┐     X-Service-Token     ┌─────────────┐
│  Виджет     │ ──────────► │  ИИ-сервис   │ ◄────────────────────── │  Платформа  │
│  (браузер)  │ ◄────────── │  :8000       │ ──────────────────────► │  :8001      │
└─────────────┘   joinUrl   └──────────────┘   webhooks, homework    └─────────────┘
       │                              │
       │  tool calls (navigate, RAG)  │
       └──────────────────────────────┘
              router.push, hwApi.*
```

**Платформа передаёт:** `courses[]`, `role`, `permissions[]`, контекст страницы.  
**ИИ не хранит** полные данные LMS — только зеркало курсов (webhook) и ChromaDB.

---

## 3. Запуск голосовой сессии

**POST** `/api/ultravox/call`  
**Auth:** `Authorization: Bearer <JWT>`

### Запрос (платформа / виджет → ИИ)

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "platform_user_id": "lms-user-42",
  "course_id": "python-100-days-ru",
  "course_name": "Python за 100 дней",
  "current_page": "Урок 5",
  "current_path": "/courses/python-100-days-ru?lesson=5",
  "page_content": "Функция def — блок кода, который можно вызывать многократно...",
  "breadcrumbs": [
    { "label": "Главная", "path": "/" },
    { "label": "Python за 100 дней", "path": "/courses/python-100-days-ru" }
  ],
  "permissions": ["navigate", "rag", "homework_hint", "notifications"],
  "available_courses": [
    {
      "id": "python-100-days-ru",
      "title": "Python за 100 дней",
      "description": "Курс для начинающих",
      "icon": "🐍"
    },
    {
      "id": "algorithms",
      "title": "Алгоритмы",
      "description": "",
      "icon": "📊"
    }
  ],
  "voice_id": null
}
```

| Поле | Обязательно | Описание |
|------|-------------|----------|
| `session_id` | нет | UUID сессии; если пусто — ИИ сгенерирует |
| `platform_user_id` | нет | ID пользователя во **внешней** LMS |
| `permissions` | нет | Явные права; если пусто — по роли из JWT |
| `available_courses` | рекомендуется | Список курсов платформы для навигации |
| `page_content` | рекомендуется | Текст экрана (до ~1500 символов) |

### Ответ (ИИ → платформа / виджет)

```json
{
  "joinUrl": "wss://fixie-test.livekit.cloud/rtc?access_token=eyJhbG...",
  "callId": "call_abc123",
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "granted_permissions": [
    "homework_hint",
    "navigate",
    "notifications",
    "rag"
  ]
}
```

Виджет подключается к `joinUrl` через Ultravox SDK. Список `granted_permissions` — фактически выданные инструменты.

---

## 4. Обновление контекста экрана (во время звонка)

**POST** `/api/ultravox/context`  
**Auth:** Bearer JWT

### Запрос

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "course_id": "python-100-days-ru",
  "course_name": "Python за 100 дней",
  "current_path": "/courses/python-100-days-ru?lesson=6",
  "current_page": "Урок 6",
  "lesson_id": "6",
  "lesson_title": "Циклы for",
  "lesson_index": 6,
  "total_lessons": 100,
  "page_content": "Цикл for перебирает элементы последовательности...",
  "homework_id": 12,
  "assignment_id": 87,
  "assignment_student": "ivanov",
  "assignment_status": "pending",
  "assignment_grade": null
}
```

### Ответ

```json
{
  "ok": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Вызывайте при каждой смене страницы (рекомендуется каждые 3–5 сек или по `router.afterEach`).

---

## 5. Навигация (резолв маршрута)

**POST** `/api/navigation/resolve`  
**Auth:** Bearer JWT (опционально)

### Запрос

```json
{
  "path_or_query": "открой python за 100 дней",
  "courses": [
    {
      "id": "python-100-days-ru",
      "title": "Python за 100 дней",
      "description": "Курс для начинающих",
      "lessons": [
        { "id": 1, "title": "День 1", "order_index": 1 },
        { "id": 2, "title": "День 2", "order_index": 2 }
      ]
    }
  ],
  "fetch_from_platform": false
}
```

Если `courses` пуст и `fetch_from_platform: true` — ИИ запросит курсы с `PLATFORM_SERVICE_URL`.

### Ответ — успех

```json
{
  "status": "ok",
  "path": "/courses/python-100-days-ru",
  "course_id": "python-100-days-ru",
  "query": {},
  "matches": [],
  "message": ""
}
```

### Ответ — неоднозначно

```json
{
  "status": "ambiguous",
  "path": null,
  "course_id": null,
  "query": {},
  "matches": [
    { "id": "python-100-days-ru", "title": "Python за 100 дней" },
    { "id": "python", "title": "Python basics" }
  ],
  "message": "Найдено несколько курсов"
}
```

### Ответ — не найдено

```json
{
  "status": "not_found",
  "path": null,
  "course_id": null,
  "query": {},
  "matches": [],
  "message": "Курс или страница не найдены"
}
```

**Правило виджета:** `router.push` только если `status === "ok"` или `status === "static"`.

---

## 6. Проверка ДЗ (только бэкенд платформы)

**POST** `/api/homework/check`  
**Auth:** `X-Service-Token: <SERVICE_API_KEY>` (не JWT пользователя)

### Запрос (платформа → ИИ)

```json
{
  "assignment_id": 87,
  "username": "ivanov",
  "homework_description": "Напишите класс Calculator с методами add и subtract...",
  "student_code": "class Calculator:\n    def add(self, a, b):\n        return a + b",
  "student_text": "Класс инкапсулирует операции над числами.",
  "content_json": "{\"intro\":\"...\",\"quiz_items\":[{\"question\":\"2+2?\",\"options\":[\"3\",\"4\"],\"correct_index\":1}]}",
  "student_quiz": { "0": 1 },
  "is_demo": false
}
```

### Ответ (ИИ → платформа)

```json
{
  "teacher_feedback": "<p>Краткий итог: работа в целом верна...</p><span class=\"hw-error\">...</span>",
  "suggested_grade": 4,
  "error_fragments": ["return a - b", "len(self.items)"]
}
```

Платформа сохраняет результат в `assignment.ai_review_json` и показывает преподавателю.

---

## 7. Webhooks (синхронизация материалов)

**Auth:** `X-Service-Token: <SERVICE_API_KEY>`

### Создание / обновление курса

**POST** `/webhook/course`

```json
{
  "id": "python-100-days-ru",
  "title": "Python за 100 дней"
}
```

**Ответ:**

```json
{
  "status": "ok",
  "nav_node": "/courses/python-100-days-ru"
}
```

### Создание / обновление урока

**POST** `/webhook/lesson`

```json
{
  "id": 5,
  "course_id": "python-100-days-ru",
  "title": "Функции",
  "content": "Функция в Python объявляется через def..."
}
```

**Ответ:**

```json
{
  "status": "ok",
  "indexed": true
}
```

---

## 8. Текстовый чат (без голоса)

**POST** `/api/chat`  
**Auth:** Bearer JWT

### Запрос

```json
{
  "message": "Объясни, что такое функция",
  "course_id": "python-100-days-ru",
  "course_name": "Python за 100 дней",
  "history": [
    { "role": "user", "content": "Привет" },
    { "role": "assistant", "content": "Привет! Чем помочь?" }
  ],
  "page_context": {
    "current_path": "/courses/python-100-days-ru?lesson=5",
    "page_content": "Текст урока на экране..."
  },
  "voice": false
}
```

### Ответ (JSON)

```json
{
  "answer": "Функция — это именованный блок кода...",
  "sources": ["lesson_5", "methodology_1"]
}
```

В ответе может быть скрытый тег `[NAVIGATE:/courses/...]` — виджет обрабатывает через `/api/navigation/validate`.

---

## 9. Audit log и аналитика

### Журнал безопасности

**GET** `/api/audit/events?days=7&action=homework_check&limit=100`  
**Auth:** Bearer JWT (только `teacher` / `admin`)

```json
{
  "period_days": 7,
  "count": 2,
  "events": [
    {
      "id": 15,
      "user_id": 3,
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "action": "voice_call_started",
      "resource": "ultravox",
      "success": true,
      "meta": {
        "role": "student",
        "permissions": ["navigate", "rag", "homework_hint"],
        "tools_count": 8,
        "path": "/courses/python-100-days-ru"
      },
      "created_at": "2026-06-09T14:30:00"
    }
  ]
}
```

### Метрики (latency, RAG, навигация)

**GET** `/api/analytics/summary?days=7`  
**POST** `/api/analytics/event` — виджет шлёт события (`voice_navigation`, `homework_hint`, …)

---

## 10. Пример кода на стороне платформы (Python)

Файл-ориентир: `platform_service/backend/app/utils/ai_client.py` (webhooks) и `app/services/ai_homework_client.py` (проверка ДЗ).

### 10.1 Конфигурация

```python
# config.py / .env
AI_SERVICE_URL = "http://ai_service:8000"
SERVICE_API_KEY = "your-shared-secret"  # одинаковый в ai_service и platform
```

### 10.2 Webhook при создании урока

```python
import requests
from app.config import settings

def notify_ai_lesson_created(lesson_id: int, course_id: str, title: str, content: str):
    url = f"{settings.AI_SERVICE_URL.rstrip('/')}/webhook/lesson"
    headers = {
        "Content-Type": "application/json",
        "X-Service-Token": settings.SERVICE_API_KEY,
    }
    payload = {
        "id": lesson_id,
        "course_id": course_id,
        "title": title,
        "content": content,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()  # {"status": "ok", "indexed": true}
```

### 10.3 ИИ-проверка домашнего задания

```python
import requests
from app.models.homework import Homework, HomeworkAssignment
from app.config import settings

def ai_review_homework(homework: Homework, assignment: HomeworkAssignment) -> dict:
    url = f"{settings.AI_SERVICE_URL.rstrip('/')}/api/homework/check"
    headers = {
        "Content-Type": "application/json",
        "X-Service-Token": settings.SERVICE_API_KEY,
    }
    payload = {
        "assignment_id": assignment.id,
        "username": assignment.student.username,
        "homework_description": homework.description,
        "student_code": assignment.student_code or "",
        "student_text": assignment.student_text or "",
        "content_json": homework.content_json or "",
        "student_quiz": assignment.student_quiz or {},
        "is_demo": bool(homework.is_demo),
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=180)
    resp.raise_for_status()
    return resp.json()
    # {
    #   "teacher_feedback": "...",
    #   "suggested_grade": 4,
    #   "error_fragments": ["..."]
    # }
```

### 10.4 Выдача JWT виджету (ваша платформа)

Виджет использует **ваш** эндпоинт логина; JWT должен содержать `sub` (user id), `role` (`student` | `teacher` | `admin`).

```python
# Пример: после login платформа отдаёт фронту token
return {
    "access_token": create_jwt(user_id=user.id, role=user.role),
    "token_type": "bearer",
    "user": {
        "id": user.id,
        "username": user.username,
        "role": user.role,
    },
}
```

---

## 11. Пример кода на стороне платформы (JavaScript / виджет)

### 11.1 Запуск голосового ассистента

```javascript
const AI_BASE = 'http://localhost:8000/api'  // или через nginx: '/api'

/** Права по роли — можно сузить для конкретного тенанта */
function permissionsForRole(role) {
  if (role === 'teacher' || role === 'admin') {
    return [
      'navigate', 'rag', 'homework_hint', 'homework_review',
      'homework_mass_review', 'journal_summary', 'homework_form', 'notifications',
    ]
  }
  return ['navigate', 'rag', 'homework_hint', 'notifications']
}

async function startVoiceAssistant({ token, user, page, courses }) {
  const sessionId = crypto.randomUUID()

  const requestBody = {
    session_id: sessionId,
    platform_user_id: String(user.id),
    course_id: page.courseId,
    course_name: page.courseName,
    current_page: page.title,
    current_path: page.path,
    page_content: page.textContent.slice(0, 1500),
    breadcrumbs: page.breadcrumbs,
    permissions: permissionsForRole(user.role),
    available_courses: courses.map((c) => ({
      id: c.id,
      title: c.title,
      description: c.description || '',
      icon: c.icon || '',
    })),
  }

  const res = await fetch(`${AI_BASE}/ultravox/call`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(requestBody),
  })

  if (!res.ok) throw new Error(await res.text())

  /** @type {{ joinUrl: string, sessionId: string, granted_permissions: string[] }} */
  const data = await res.json()

  console.log('Granted permissions:', data.granted_permissions)
  // Подключение Ultravox SDK к data.joinUrl
  return data
}
```

### 11.2 Безопасная навигация перед router.push

```javascript
async function safeNavigate(pathOrQuery, courses, router) {
  const res = await fetch(`${AI_BASE}/navigation/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      path_or_query: pathOrQuery,
      courses: courses.map((c) => ({
        id: c.id,
        title: c.title,
        description: c.description || '',
        lessons: c.lessons || [],
      })),
    }),
  })
  const data = await res.json()

  if (data.status === 'ok' || data.status === 'static') {
    await router.push(data.path)
    return { ok: true, path: data.path }
  }
  if (data.status === 'ambiguous') {
    return { ok: false, ambiguous: true, matches: data.matches }
  }
  return { ok: false, message: data.message }
}
```

### 11.3 Подсказка по ДЗ (через API платформы, не напрямую в ИИ)

Подсказки и проверки ДЗ идут **через ваш бэкенд** — там лимиты, 403, пост-фильтр.

```javascript
async function requestHomeworkHint(token, assignmentId, draft) {
  const res = await fetch(`http://localhost:8001/api/homework/assignments/${assignmentId}/hint`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      student_code: draft.code,
      student_text: draft.text,
      student_quiz: draft.quiz,
    }),
  })
  if (res.status === 429) {
    const err = await res.json()
    throw new Error(err.detail)  // лимит подсказок / cooldown
  }
  if (!res.ok) throw new Error(await res.text())
  /** @type {{ hint: string }} */
  return res.json()
}
```

---

## 12. События tool calls (виджет выполняет локально)

Ultravox вызывает инструменты **в браузере**. Платформа регистрирует обработчики:

| Tool | Действие виджета |
|------|------------------|
| `navigatePage` | `navigation/resolve` → `router.push` |
| `openLesson` | переход на `/courses/{id}?lesson_idx=N` |
| `openAdjacentLesson` | `navigation/adjacent-lesson` |
| `queryKnowledgeBase` | `POST /api/ultravox/rag` |
| `getHomeworkHint` | `POST /api/homework/.../hint` (платформа) |
| `reviewHomework` | `POST /api/homework/.../ai-review` (платформа, confirm=true) |
| `getPageContext` | вернуть `current_path` + `page_content` |

### Пример payload tool `openLesson` (Ultravox → виджет)

```json
{
  "course_id": "python-100-days-ru",
  "lesson_number": 5,
  "highlight_text": "Функция def объявляется"
}
```

### Пример ответа виджета tool

```json
{
  "result": "Переход на урок 5 выполнен.",
  "responseType": "tool-response",
  "agentReaction": "LISTENS"
}
```

---

## 13. Чеклист интеграции для новой LMS

1. Настроить `SERVICE_API_KEY` в обоих `.env`.
2. При CRUD курсов/уроков — webhooks на `/webhook/course`, `/webhook/lesson`.
3. Виджет: JWT + `permissions[]` + `available_courses[]` в `/api/ultravox/call`.
4. Навигация только через `/api/navigation/resolve`.
5. ДЗ: подсказки и проверки через **ваш** REST API (не обходить 403).
6. Мониторинг: `/api/audit/events`, `/api/analytics/summary`.

---

## 14. Переменные окружения

| Переменная | Сервис | Описание |
|------------|--------|----------|
| `SERVICE_API_KEY` | оба | Секрет platform ↔ AI |
| `AI_SERVICE_URL` | platform | URL ИИ (`http://ai_service:8000`) |
| `PLATFORM_SERVICE_URL` | ai | URL LMS для sync курсов |
| `JWT_SECRET` | оба | Подпись пользовательских токенов |
| `ULTRAVOX_API_KEY` | ai | Ключ Ultravox (голос) |
