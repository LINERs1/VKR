"""Пост-фильтр подсказок по ДЗ — отсекает готовые решения."""

from __future__ import annotations

import re

_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_CODE_LINE_RE = re.compile(
    r"^\s*(def |class |import |from |return |for |while |if |elif |else:)",
    re.MULTILINE,
)
_ANSWER_LEAK_RE = re.compile(
    r"правильн\w*\s+ответ|верный\s+вариант|correct\s+answer|ответ\s*[:—-]\s*[A-Dа-г]",
    re.IGNORECASE,
)

_SAFE_FALLBACK = (
    "Попробуй разбить задачу на шаги: что должна делать каждая часть? "
    "Проверь имена переменных и граничные случаи — без готового кода."
)


def filter_homework_hint(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return _SAFE_FALLBACK

    if _CODE_BLOCK_RE.search(text):
        return _SAFE_FALLBACK

    if len(_CODE_LINE_RE.findall(text)) >= 2:
        return _SAFE_FALLBACK

    if _ANSWER_LEAK_RE.search(text):
        return "Подумай, какой вариант лучше соответствует условию — и почему?"

    if len(text) > 600:
        text = text[:600].rsplit(" ", 1)[0] + "…"

    return text
