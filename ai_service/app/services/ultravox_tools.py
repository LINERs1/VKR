"""Allowlist голосовых инструментов Ultravox по роли пользователя."""

_NAVIGATE_TOOL = {
    "temporaryTool": {
        "modelToolName": "navigatePage",
        "description": (
            "Переводит пользователя на страницу платформы (курс, журнал, профиль, главная, ДЗ). "
            "ДЛЯ УРОКОВ НЕ ИСПОЛЬЗОВАТЬ! Для уроков используй openLesson. "
            "ВНИМАНИЕ: Если пользователь просит открыть курс, которого нет в списке доступных, "
            "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО переходить на другой курс или выдумывать пути. "
            "Просто скажи словами, что такого курса нет. "
            "Сначала одной фразой по-русски скажи, куда переходишь («Открываю журнал»), затем вызови инструмент. "
            "После вызова не повторяй переход и не комментируй смену экрана. "
            "Не произноси navigate, NAVIGATE, path, URL или слэши."
        ),
        "dynamicParameters": [
            {
                "name": "path",
                "location": "PARAMETER_LOCATION_BODY",
                "schema": {
                    "description": "Точный маршрут из списка доступных. ЗАПРЕЩЕНО выдумывать маршруты самостоятельно.",
                    "type": "string",
                },
                "required": True,
            },
        ],
        "client": {},
    }
}

_OPEN_LESSON_TOOL = {
    "temporaryTool": {
        "modelToolName": "openLesson",
        "description": (
            "Открывает конкретный урок курса. "
            "Используй ТОЛЬКО этот инструмент для перехода на уроки (вместо navigatePage). "
            "Сначала скажи «Открываю урок», затем вызови инструмент."
        ),
        "dynamicParameters": [
            {
                "name": "course_id",
                "location": "PARAMETER_LOCATION_BODY",
                "schema": {
                    "description": "ID курса (например, 'python-100-days-ru', 'react-30-days-ru').",
                    "type": "string",
                },
                "required": True,
            },
            {
                "name": "lesson_number",
                "location": "PARAMETER_LOCATION_BODY",
                "schema": {
                    "description": "Порядковый номер урока (например, 1, 2, 5).",
                    "type": "integer",
                },
                "required": True,
            },
            {
                "name": "highlight_text",
                "location": "PARAMETER_LOCATION_BODY",
                "schema": {
                    "description": "Кусок текста (от 1 до 5 слов) для подсветки на странице.",
                    "type": "string",
                },
                "required": False,
            },
        ],
        "client": {},
    }
}

_ADJACENT_LESSON_TOOL = {
    "temporaryTool": {
        "modelToolName": "openAdjacentLesson",
        "description": (
            "Переключает на следующий или предыдущий урок текущего курса. "
            "Используй при «следующий урок», «предыдущий», «листай дальше», «вернись назад». "
            "Не вызывай на главной без открытого курса."
        ),
        "dynamicParameters": [
            {
                "name": "delta",
                "location": "PARAMETER_LOCATION_BODY",
                "schema": {
                    "description": "1 — следующий урок, -1 — предыдущий",
                    "type": "integer",
                },
                "required": True,
            },
        ],
        "client": {},
    }
}

_PAGE_CONTEXT_TOOL = {
    "temporaryTool": {
        "modelToolName": "getPageContext",
        "description": (
            "Возвращает актуальное местоположение пользователя на сайте и текст, "
            "который сейчас виден на экране. Вызывай после перехода на другую страницу "
            "или если пользователь спрашивает «где я», «что на экране»."
        ),
        "client": {},
    }
}

_RAG_TOOL = {
    "temporaryTool": {
        "modelToolName": "queryKnowledgeBase",
        "description": (
            "Ищет информацию в материалах курса по смысловому сходству. "
            "Используй, когда пользователь задаёт вопросы по теме курса "
            "или просит объяснить тему в учебных материалах."
        ),
        "dynamicParameters": [
            {
                "name": "query",
                "location": "PARAMETER_LOCATION_BODY",
                "schema": {
                    "description": "Поисковый запрос для поиска в материалах курса",
                    "type": "string",
                },
                "required": True,
            },
        ],
        "client": {},
    }
}

_TEACHER_TOOLS = [
    {
        "temporaryTool": {
            "modelToolName": "reviewHomework",
            "description": (
                "Запускает автоматическую ИИ-проверку домашнего задания выбранного ученика. "
                "Сначала спроси подтверждение («Проверить работу … с помощью ИИ?»). "
                "Только после явного «да» вызови с confirm=true. "
                "Работа должна быть в статусе submitted; если graded — не вызывай."
            ),
            "dynamicParameters": [
                {
                    "name": "confirm",
                    "location": "PARAMETER_LOCATION_BODY",
                    "schema": {
                        "description": "true — только после явного согласия преподавателя",
                        "type": "boolean",
                    },
                    "required": False,
                },
            ],
            "client": {},
        }
    },
    {
        "temporaryTool": {
            "modelToolName": "reviewAllHomeworks",
            "description": (
                "Запускает массовую фоновую ИИ-проверку всех несданных домашних заданий, "
                "которые ещё не проверялись ИИ. "
                "Вызывай, если преподаватель просит «проверь все ДЗ»."
            ),
            "client": {},
        }
    },
    {
        "temporaryTool": {
            "modelToolName": "getTeacherSummary",
            "description": (
                "Сводка журнала: средний балл, кто не сдал ДЗ, что ждёт проверки. "
                "Вызывай на вопросы «кто не сдал», «средний балл», «что на проверке»."
            ),
            "client": {},
        }
    },
    {
        "temporaryTool": {
            "modelToolName": "fillHomeworkForm",
            "description": (
                "Заполняет поля формы создания домашнего задания в Мастерской ДЗ. "
                "Вызывай когда преподаватель просит создать задание или заполнить шаблон."
            ),
            "dynamicParameters": [
                {
                    "name": "title",
                    "location": "PARAMETER_LOCATION_BODY",
                    "schema": {"description": "Название домашнего задания", "type": "string"},
                    "required": False,
                },
                {
                    "name": "intro",
                    "location": "PARAMETER_LOCATION_BODY",
                    "schema": {"description": "Описание задания", "type": "string"},
                    "required": False,
                },
                {
                    "name": "code_template",
                    "location": "PARAMETER_LOCATION_BODY",
                    "schema": {"description": "Шаблон кода с TODO", "type": "string"},
                    "required": False,
                },
                {
                    "name": "written_part",
                    "location": "PARAMETER_LOCATION_BODY",
                    "schema": {"description": "Письменная часть", "type": "string"},
                    "required": False,
                },
                {
                    "name": "quiz_items",
                    "location": "PARAMETER_LOCATION_BODY",
                    "schema": {
                        "description": 'Тесты: [{"question":"...","options":["A","B"],"correct_index":0}]',
                        "type": "string",
                    },
                    "required": False,
                },
            ],
            "client": {},
        }
    },
]

_STUDENT_TOOLS = [
    {
        "temporaryTool": {
            "modelToolName": "getHomeworkReminders",
            "description": (
                "Список несданных домашних заданий ученика. "
                "Вызывай, если ученик спрашивает «что мне сделать», «какие ДЗ остались»."
            ),
            "client": {},
        }
    },
    {
        "temporaryTool": {
            "modelToolName": "getHomeworkHint",
            "description": (
                "Сократическая подсказка по текущему домашнему заданию без готового решения. "
                "Вызывай, если ученик просит подсказку на странице ДЗ."
            ),
            "client": {},
        }
    },
]

_COMMON_TOOLS = [
    {
        "temporaryTool": {
            "modelToolName": "getNotifications",
            "description": (
                "Получает список новых оповещений пользователя. "
                "Оповещения содержат ссылки для navigatePage."
            ),
            "client": {},
        }
    },
    {
        "temporaryTool": {
            "modelToolName": "clearNotifications",
            "description": "Очищает все оповещения пользователя.",
            "client": {},
        }
    },
]


def build_voice_tools(role: str | None, granted: set[str] | None = None) -> list:
    """Строгий allowlist инструментов по роли и permissions[]."""
    from app.services.permissions import filter_tools_by_permissions, resolve_permissions

    role_norm = (role or "student").lower()
    is_teacher = role_norm in ("teacher", "admin")
    perms = granted if granted is not None else resolve_permissions(role_norm)

    tools = [
        _RAG_TOOL,
        _PAGE_CONTEXT_TOOL,
        _NAVIGATE_TOOL,
        _OPEN_LESSON_TOOL,
        _ADJACENT_LESSON_TOOL,
    ]

    if is_teacher:
        tools.extend(_TEACHER_TOOLS)
    elif role_norm == "student":
        tools.extend(_STUDENT_TOOLS)

    tools.extend(_COMMON_TOOLS)
    return filter_tools_by_permissions(tools, perms)
