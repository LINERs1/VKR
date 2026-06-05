# API Интеграции Голосового ИИ-ассистента

В этом документе описаны все входящие HTTP-запросы (от образовательной платформы к нашему ИИ-серверу), наши ответы на них, а также JSON-структуры событий, которые ИИ отправляет на фронтенд платформы для выполнения действий.

Все запросы к ИИ-серверу должны содержать заголовок авторизации:
`Authorization: Bearer <jwt_token>` (токен подписан общим секретным ключом).

---

## 1. Запуск голосового звонка
Вызывается фронтендом платформы в момент, когда пользователь нажимает кнопку вызова ассистента.

**POST** `/api/ultravox/start`

**Запрос (Фронтенд → ИИ):**
```json
{
  "user_id": 1,
  "username": "st",
  "role": "student",
  "course_id": "python",
  "course_name": "Python для начинающих",
  "current_path": "/courses/python?lesson=1",
  "lesson_id": "1",
  "lesson_index": 1
}
```

**Ответ (ИИ → Фронтенд):**
```json
{
  "join_url": "wss://fixie-test.livekit.cloud/rtc?access_token=eyJhbGciOiJIUzI1NiIsInR5..."
}
```
*Фронтенд использует полученный `join_url` для подключения к голосовому звонку через Ultravox SDK.*

---

## 2. Передача контекста экрана
Вызывается фронтендом платформы каждые 5 секунд во время активного звонка, чтобы ИИ "видел" актуальную страницу.

**POST** `/api/ultravox/context`

**Запрос (Фронтенд → ИИ):**
```json
{
  "session_id": "abc123_uuid",
  "course_id": "python",
  "course_name": "Python для начинающих",
  "current_path": "/courses/python?lesson=2",
  "current_page": "lesson",
  "lesson_id": "2",
  "lesson_title": "Переменные и типы данных",
  "lesson_index": 2,
  "total_lessons": 5,
  "page_content": "Переменная — это именованная область памяти для хранения данных. В Python переменная создаётся в момент присваивания..."
}
```

**Ответ (ИИ → Фронтенд):**
```json
{
  "ok": true
}
```

---

## 3. Webhook: Обновление учебных материалов
Вызывается бэкендом платформы каждый раз, когда преподаватель создаёт или редактирует урок. ИИ использует это для пополнения векторной базы (ChromaDB) и построения графа навигации.

**POST** `/webhook/lesson`

**Запрос (Платформа → ИИ):**
```json
{
  "event": "lesson_created",
  "lesson_id": 3,
  "course_id": "python",
  "title": "Циклы и условия",
  "content": "Цикл for используется для перебора элементов последовательности. Например: for i in range(5)..."
}
```

**Ответ (ИИ → Платформа):**
```json
{
  "ok": true,
  "indexed_chunks": 4,
  "nav_node_created": true
}
```

---

## 4. Получение аналитики
Вызывается бэкендом или дашбордом платформы для отображения статистики работы голосового ассистента.

### 4.1 Сводный отчёт
**GET** `/api/analytics/summary?days=7`

**Ответ (ИИ → Платформа):**
```json
{
  "period_days": 7,
  "total_events": 142,
  "chat_rag": {
    "count": 87,
    "avg_ms": 1240,
    "min_ms": 430,
    "max_ms": 3200
  },
  "homework_hint": {
    "count": 23,
    "avg_ms": 2100,
    "min_ms": 890,
    "max_ms": 4500
  },
  "voice_navigation": {
    "success": 29,
    "failed": 3,
    "success_rate": 0.91
  }
}
```

### 4.2 Детальный отчёт
**GET** `/api/analytics/detailed?days=30`

**Ответ (ИИ → Платформа):**
```json
{
  "period_days": 30,
  "activity_by_day": [
    { "date": "2026-06-01", "voice_calls": 12, "text_messages": 45 },
    { "date": "2026-06-02", "voice_calls": 15, "text_messages": 50 }
  ],
  "llm_performance": [
    { "date": "2026-06-01", "avg_response_ms": 1100 },
    { "date": "2026-06-02", "avg_response_ms": 1150 }
  ],
  "active_users_ranking": [
    { "user_id": 1, "username": "st", "interactions": 120, "last_active": "2026-06-04T10:00:00Z" }
  ]
}
```

---

## 5. Вызовы функций ИИ (События SDK)
Это не HTTP-запросы, а JSON-объекты (payloads), которые Ultravox SDK генерирует в браузере платформы, когда ИИ решает выполнить действие. Платформа слушает эти события.

### 5.1 Команда: Переход на страницу
Событие: `eduai-navigate`
**Payload (ИИ → Фронтенд):**
```json
{
  "path": "/courses/python?lesson=2"
}
```

### 5.2 Команда: Подсветка текста
Событие: `eduai-highlight-text`
**Payload (ИИ → Фронтенд):**
```json
{
  "text": "В Python переменная создаётся в момент присваивания"
}
```

### 5.3 Команда: Заполнение формы ДЗ (режим преподавателя)
Событие: `eduai-fill-homework`
**Payload (ИИ → Фронтенд):**
```json
{
  "title": "Списки и циклы",
  "intro": "Напишите программу, которая перебирает список...",
  "code_template": "def process_list(items):\n    pass",
  "written_part": ""
}
```

### 5.4 Запрос контекста (ИИ запрашивает у фронтенда)
Событие: `tool-call` (name: `getPageContext`)
**Ответ платформы (Фронтенд → ИИ):**
```json
{
  "current_path": "/courses/python?lesson=3",
  "page_content": "Здесь находится текст 3-го урока про циклы..."
}
```
