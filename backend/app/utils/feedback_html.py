"""Нормализация HTML-подсветки ошибок в отзыве преподавателя."""

import re

_HW_ERROR_CLASS = 'hw-error'
_INLINE_RED_SPAN = re.compile(
    r"<span\s+style=['\"][^'\"]*#ef4444[^'\"]*['\"][^>]*>(.*?)</span>",
    re.IGNORECASE | re.DOTALL,
)
_HW_ERROR_SPAN = re.compile(
    r'<span\s+class=["\']hw-error["\'][^>]*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")


def normalize_teacher_feedback(text: str) -> str:
    """Приводит отзыв к виду с <span class=\"hw-error\"> для красной подсветки в UI."""
    if not text:
        return ""

    out = text.strip()
    out = _INLINE_RED_SPAN.sub(r'<span class="hw-error">\1</span>', out)

    if _HW_ERROR_SPAN.search(out):
        return out

    # Модель часто выделяет ошибки жирным markdown вместо HTML
    if _BOLD.search(out):
        out = _BOLD.sub(r'<span class="hw-error">\1</span>', out)
        return out

    # Подсветка типичных фрагментов, если модель не дала разметку
    for phrase in ("len(self.grade)", ">= 5", "возвратом нуля", "порог 5", ">= 5.0"):
        if phrase.lower() in out.lower() and f'hw-error">{phrase}' not in out:
            idx = out.lower().find(phrase.lower())
            if idx != -1:
                orig = out[idx : idx + len(phrase)]
                out = (
                    out[:idx]
                    + f'<span class="hw-error">{orig}</span>'
                    + out[idx + len(phrase) :]
                )

    return out


def extract_error_fragments(text: str) -> list[str]:
    """Фрагменты из span hw-error — для подсветки в ответе ученика."""
    if not text:
        return []
    normalized = normalize_teacher_feedback(text)
    seen: set[str] = set()
    out: list[str] = []
    for m in _HW_ERROR_SPAN.finditer(normalized):
        frag = m.group(1).strip()
        if len(frag) >= 2 and frag not in seen:
            seen.add(frag)
            out.append(frag)
    return sorted(out, key=len, reverse=True)
