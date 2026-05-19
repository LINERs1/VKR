"""Сборка описания ДЗ из структуры мастерской."""

import json
from typing import Any

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


def dump_content(data: dict[str, Any]) -> str:
    merged = dict(DEFAULT_CONTENT)
    merged.update(data or {})
    if "quiz_items" in merged:
        merged["quiz_items"] = _normalize_quiz_items(merged.get("quiz_items"))
    return json.dumps(merged, ensure_ascii=False)


def _format_quiz_markdown(quiz_items: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, q in enumerate(quiz_items):
        qtext = (q.get("question") or "").strip()
        opts = q.get("options") or []
        if not qtext and not opts:
            continue
        n = i + 1
        lines.append(f"**Вопрос {n}.** {qtext}")
        for j, opt in enumerate(opts):
            letter = chr(ord("A") + j)
            lines.append(f"- {letter}) {opt}")
        lines.append("")
    return "\n".join(lines).strip()


def build_student_description(content: dict[str, Any], include_reference: bool = False) -> str:
    """Текст задания для ученика (и поле homework.description)."""
    c = parse_content(json.dumps(content) if isinstance(content, dict) else content)
    quiz_block = _format_quiz_markdown(c.get("quiz_items") or [])
    parts = [
        f"# {c.get('title_hint', '')}".strip() if c.get("title_hint") else "",
        c["intro"].strip(),
        "",
        "## Часть 1. Код",
        f"Файл: `{c['code_filename']}`",
        "",
        "Шаблон для старта:",
        "```python",
        c["code_template"].rstrip(),
        "```",
        "",
        "## Часть 2. Тесты (вопросы с вариантами ответов)",
        quiz_block if quiz_block else "(Вопросы не заданы — преподаватель добавит их в мастерской.)",
        "",
    ]
    tests_code = (c.get("tests_code") or "").strip()
    if tests_code:
        parts.extend(
            [
                "### Дополнительно: пример автотестов (pytest, по желанию)",
                "",
                "```python",
                tests_code,
                "```",
                "",
            ]
        )
    parts.extend(
        [
            "## Часть 3. Письменная часть",
            c["written_part"].strip(),
        ]
    )
    if include_reference and c.get("reference_code", "").strip():
        parts.extend(
            [
                "",
                "---",
                "<details><summary>Эталон (только преподаватель)</summary>",
                "",
                "```python",
                c["reference_code"].rstrip(),
                "```",
                "</details>",
            ]
        )
    return "\n".join(p for p in parts if p is not None).strip()
