"""Права ролей для промптов чата и голосового ассистента."""


def build_role_capabilities_prompt(role: str | None, *, voice: bool = False) -> str:
    """Явные возможности и ограничения по роли (student / teacher)."""
    if role == "teacher":
        return _TEACHER_CAPABILITIES_VOICE if voice else _TEACHER_CAPABILITIES
    if role == "student":
        return _STUDENT_CAPABILITIES_VOICE if voice else _STUDENT_CAPABILITIES
    return _GUEST_CAPABILITIES


_TEACHER_CAPABILITIES = """### ПРАВА ПОЛЬЗОВАТЕЛЯ (ПРЕПОДАВАТЕЛЬ)
ДОСТУПНО:
- Журнал успеваемости (/journal): просмотр оценок.
- Мастерская домашних заданий.
- Просмотр работ учеников.
- Все курсы и уроки, материалы курса (queryKnowledgeBase).
- Свой профиль (/profile).

НЕДОСТУПНО (не предлагай и не имитируй):
- Сдавать ДЗ от имени ученика.
Если просят «мою подсказку по ДЗ как ученику» — объясни, что вы преподаватель."""

_STUDENT_CAPABILITIES = """### ПРАВА ПОЛЬЗОВАТЕЛЯ (УЧЕНИК)
ДОСТУПНО:
- Свои домашние задания: просмотр, сдача.
- Курсы и уроки, материалы курса (queryKnowledgeBase).
- Главная (/), профиль (/profile), список своих ДЗ (/homeworks).

НЕДОСТУПНО (категорически — не навигация, не выдумывай данные):
- Журнал успеваемости (/journal) — только у преподавателя. На просьбу открыть журнал скажи, что раздел доступен преподавателю.
- Мастерская ДЗ, проверка чужих работ, выставление оценок.
- Просмотр ответов и оценок других учеников.
Если просят проверить чужую работу или журнал — вежливо откажи и предложи свои ДЗ или курс."""

_TEACHER_CAPABILITIES_VOICE = _TEACHER_CAPABILITIES

_STUDENT_CAPABILITIES_VOICE = _STUDENT_CAPABILITIES

_GUEST_CAPABILITIES = """### ПРАВА (ГОСТЬ, не авторизован)
Доступны только общие вопросы о платформе и курсах. Журнал, ДЗ и проверка — после входа."""
