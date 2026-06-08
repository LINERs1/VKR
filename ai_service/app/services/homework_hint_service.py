"""Сократические подсказки по ДЗ (без готового решения)."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.models.homework import Homework, HomeworkAssignment
from app.services.homework_template_service import parse_content
from app.services.llm_service import get_llm

logger = logging.getLogger(__name__)

_SYSTEM = """Ты — {assistant}, помощник ученика на платформе EduAI.
Дай ОДНУ короткую сократическую подсказку по домашнему заданию.

СТРОГО ЗАПРЕЩЕНО:
- писать готовое решение или полный код;
- давать готовые ответы на тесты с вариантами;
- переписывать код ученика за него.

НУЖНО:
- 2–4 предложения на русском;
- наводящий вопрос или намёк на следующий шаг;
- если видишь типичную ошибку — мягко намекни, не называя готовую строку кода целиком.
"""


def _quiz_hint_block(content: dict, answers: dict | None) -> str:
    raw_items = content.get("quiz_items") or []
    if not raw_items:
        return ""
    answers = answers or {}
    lines: list[str] = ["", "ТЕСТОВАЯ ЧАСТЬ (вопросы с вариантами):"]
    for i, q in enumerate(raw_items):
        if not isinstance(q, dict):
            continue
        question = (q.get("question") or "").strip()
        opts = q.get("options") or []
        if not isinstance(opts, list):
            opts = []
        if not question and not opts:
            continue
        lines.append(f"Вопрос {i + 1}: {question}")
        for j, opt in enumerate(opts):
            lines.append(f"  {chr(ord('A') + j)}) {opt}")
        picked_raw = answers.get(str(i), answers.get(i))
        try:
            picked = int(picked_raw) if picked_raw is not None else None
        except (TypeError, ValueError):
            picked = None
        if picked is not None and 0 <= picked < len(opts):
            lines.append(f"  Выбор ученика: {chr(ord('A') + picked)}) {opts[picked]}")
        else:
            lines.append("  Выбор ученика: (ещё не выбрано)")
    return "\n".join(lines)


def generate_homework_hint(
    homework: Homework,
    assignment: HomeworkAssignment,
    *,
    draft_code: str | None = None,
    draft_text: str | None = None,
    draft_quiz: dict | None = None,
) -> str:
    content = parse_content(homework.content_json) if homework.content_json else {}
    intro = (content.get("intro") or homework.description or "")[:800]
    code = (draft_code if draft_code is not None else assignment.student_code or content.get("code_template") or "").strip()[:2000]
    text = (draft_text if draft_text is not None else assignment.student_text or "").strip()[:600]
    quiz_answers = draft_quiz if draft_quiz is not None else (assignment.student_quiz or {})
    quiz_block = _quiz_hint_block(content, quiz_answers)

    user = f"""ЗАДАНИЕ:
{intro}
{quiz_block}

КОД УЧЕНИКА (черновик):
```
{code or '(пока пусто)'}
```

ПИСЬМЕННАЯ ЧАСТЬ (черновик):
{text or '(пока пусто)'}

Дай одну подсказку — что подумать или проверить дальше."""

    from app.config import settings

    llm = get_llm()
    messages = [
        SystemMessage(content=_SYSTEM.format(assistant=settings.ASSISTANT_NAME)),
        HumanMessage(content=user),
    ]
    raw = llm.invoke(messages).content.strip()
    logger.info("Homework hint assignment=%s len=%s", assignment.id, len(raw))
    return raw
