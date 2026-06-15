"""ИИ-проверка домашних заданий для преподавателя."""

import json
import logging
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.constants import HOMEWORK_REVIEW_TEXT_LIMIT
from app.services.llm_service import get_homework_llm
from app.utils.feedback_html import extract_error_fragments, normalize_teacher_feedback

DEFAULT_CONTENT: dict[str, Any] = {
    "intro": "Опишите цель задания и критерии оценки.",
    "code_filename": "solution.py",
    "code_template": "def solve():\n    pass\n",
    "tests_code": "",
    "quiz_items": [],
    "written_part": "1. Ответьте своими словами на вопрос…\n2. …",
    "reference_code": "",
}


def _normalize_quiz_items(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        opts = item.get("options") or []
        if not isinstance(opts, list):
            opts = []
        opts = [str(x).strip() for x in opts if str(x).strip()]
        ci = item.get("correct_index", 0)
        try:
            ci = int(ci)
        except (TypeError, ValueError):
            ci = 0
        lid = item.get("lesson_id")
        try:
            lesson_id = int(lid) if lid is not None and lid != "" else None
        except (TypeError, ValueError):
            lesson_id = None
        out.append(
            {
                "question": str(item.get("question", "") or "").strip(),
                "options": opts,
                "correct_index": ci,
                "topic": str(item.get("topic", "") or "").strip(),
                "lesson_id": lesson_id,
            }
        )
    return out


def parse_content(raw: str | None) -> dict[str, Any]:
    if not raw:
        return dict(DEFAULT_CONTENT)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return dict(DEFAULT_CONTENT)
        out = dict(DEFAULT_CONTENT)
        for k in DEFAULT_CONTENT:
            if k not in data:
                continue
            if k == "quiz_items":
                out[k] = _normalize_quiz_items(data[k])
            else:
                out[k] = data[k]
        return out
    except json.JSONDecodeError:
        return dict(DEFAULT_CONTENT)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "homework" / "demo_grade_average"

_SYSTEM = """Ты — ассистент преподавателя на платформе EduAI.
Проверь домашнее задание ученика: код, письменную часть, а также тесты с вариантами ответов — НО ТОЛЬКО если они явно указаны в задании ниже.

ПРАВИЛА ОФОРМЛЕНИЯ (обязательно):
1. Отвечай ТОЛЬКО на русском.
2. Каждую ошибку обязательно оберни ТОЛЬКО так (без markdown **):
   <span class="hw-error">фрагмент с ошибкой</span>
   Пример: <span class="hw-error">len(self.grade)</span> вместо len(self.grades).
3. Минимум 2–4 таких span, если есть ошибки. Не пиши теги внутри ```кода```.
4. Структура ответа (пропускай пункты, которых нет в задании):
   - Краткий итог (1–2 предложения)
   - Разбор кода (пункты)
   - Разбор тестов с вариантами — ТОЛЬКО если тесты были в задании
   - Разбор письменной части (пункты)
   - Рекомендации
   - В конце: ПРЕДЛАГАЕМАЯ_ОЦЕНКА: N  (целое от 1 до 5)
   - Следующей строкой: ОШИБКИ_JSON: ["точная подстрока из кода/текста ученика", ...]
     (минимум 2 строки, скопируй символ в символ: len(self.grade), >= 5, 4.0 и т.д.)
5. Не выдумывай ошибки и не придумывай тесты которых нет; если работа идеальна — похвали и поставь 5.
6. Не используй markdown-заголовки с # и не заменяй span на **жирный**.
"""


_GRADE_RE = re.compile(r"ПРЕДЛАГАЕМАЯ_ОЦЕНКА:\s*([1-5])", re.IGNORECASE)
_ERRORS_JSON_RE = re.compile(r"ОШИБКИ_JSON:\s*(\[[\s\S]*?\])", re.IGNORECASE)


def _parse_errors_json(raw: str) -> tuple[str, list[str]]:
    m = _ERRORS_JSON_RE.search(raw)
    if not m:
        return raw, []
    try:
        items = json.loads(m.group(1))
        frags = [str(x).strip() for x in items if isinstance(x, (str, int, float)) and str(x).strip()]
    except json.JSONDecodeError:
        frags = []
    cleaned = _ERRORS_JSON_RE.sub("", raw).strip()
    return cleaned, frags


def _merge_fragments(*lists: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for lst in lists:
        for f in sorted(lst, key=len, reverse=True):
            if f and f not in seen:
                seen.add(f)
                out.append(f)
    return out


def _load_reference_tests() -> str:
    path = DATA_DIR / "test_calculator.py"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def _quiz_review_block_raw(content_json: str | None, student_quiz: dict | None) -> str:
    if not content_json:
        return ""
    raw_items = parse_content(content_json).get("quiz_items") or []
    if not raw_items:
        return ""
    answers = student_quiz or {}
    lines: list[str] = ["---", "ТЕСТЫ С ВАРИАНТАМИ (эталон и ответы ученика):"]
    for i, q in enumerate(raw_items):
        if not isinstance(q, dict):
            continue
        question = (q.get("question") or "").strip()
        opts = q.get("options") or []
        if not isinstance(opts, list):
            opts = []
        try:
            correct = int(q.get("correct_index", 0))
        except (TypeError, ValueError):
            correct = 0
        picked_raw = answers.get(str(i))
        try:
            picked = int(picked_raw) if picked_raw is not None else None
        except (TypeError, ValueError):
            picked = None
        ok = picked is not None and 0 <= picked < len(opts) and picked == correct
        letter_ok = chr(ord("A") + correct) if 0 <= correct < len(opts) else "?"
        letter_p = chr(ord("A") + picked) if picked is not None and 0 <= picked < len(opts) else "—"
        lines.append(f"Вопрос {i + 1}: {question}")
        for j, opt in enumerate(opts):
            mark = " [верный]" if j == correct else ""
            lines.append(f"  {chr(ord('A') + j)}) {opt}{mark}")
        lines.append(f"  Ответ ученика: {letter_p} (верный вариант: {letter_ok})")
        lines.append(f"  Итог по вопросу: {'верно' if ok else 'ошибка'}")
        lines.append("")
    return "\n".join(lines)


def review_assignment_raw(
    *,
    assignment_id: int,
    username: str,
    homework_description: str,
    student_code: str = "",
    student_text: str = "",
    content_json: str = "",
    student_quiz: dict | None = None,
    is_demo: bool = False,
) -> dict:
    tests_section = ""
    if is_demo:
        tests_block = _load_reference_tests()
        if tests_block:
            tests_section = (
                f"\n\nЭТАЛОННЫЕ АВТОТЕСТЫ (pytest):\n```python\n{tests_block}\n```\n"
            )

    quiz_section = _quiz_review_block_raw(content_json or None, student_quiz)

    user_prompt = f"""ЗАДАНИЕ:
{homework_description[:HOMEWORK_REVIEW_TEXT_LIMIT]}

---
КОД УЧЕНИКА ({username}):
```python
{student_code or '(не сдан)'}
```

---
ПИСЬМЕННАЯ ЧАСТЬ:
{student_text or '(не сдана)'}
{quiz_section}
{tests_section}
"""

    llm = get_homework_llm()
    messages = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=user_prompt),
    ]
    raw = llm.invoke(messages).content.strip()

    suggested_grade = None
    m = _GRADE_RE.search(raw)
    if m:
        suggested_grade = int(m.group(1))
        raw = _GRADE_RE.sub("", raw).strip()

    raw, json_frags = _parse_errors_json(raw)
    feedback = normalize_teacher_feedback(raw)
    error_fragments = _merge_fragments(json_frags, extract_error_fragments(feedback))

    logger.info(
        "AI homework review assignment %s grade=%s fragments=%s",
        assignment_id,
        suggested_grade,
        len(error_fragments),
    )
    return {
        "teacher_feedback": feedback,
        "suggested_grade": suggested_grade,
        "error_fragments": error_fragments,
    }
