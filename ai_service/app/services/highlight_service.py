"""Валидация и санитизация highlight_text для подсветки фрагментов урока."""

from __future__ import annotations

import re

_HTML_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")

HIGHLIGHT_MIN_WORDS = 1
HIGHLIGHT_MIN_WORDS_CODE = 1
HIGHLIGHT_MAX_WORDS = 8

_CODE_HINTS = frozenset({"for", "in", "while", "def", "class", "import", "return", "if", "else"})


def sanitize_highlight_text(text: str | None) -> str:
    if not text:
        return ""
    t = _HTML_RE.sub(" ", str(text))
    t = _URL_RE.sub(" ", t)
    t = _CODE_FENCE_RE.sub(" ", t)
    # inline `code` оставляем — иначе теряются фрагменты for/in из урока
    t = re.sub(r"[*_#]", " ", t)
    words = [w for w in t.split() if w.strip()]
    if not words:
        return ""
    min_words = (
        HIGHLIGHT_MIN_WORDS_CODE
        if any(w.lower().rstrip(":,") in _CODE_HINTS for w in words[:5])
        else HIGHLIGHT_MIN_WORDS
    )
    if len(words) < min_words:
        return ""
    return " ".join(words[:HIGHLIGHT_MAX_WORDS])


def normalize_for_match(text: str) -> str:
    clean = re.sub(
        r"[.,/#!$%^&*;:{}=\-_`~()«»\"'\n\r\t]",
        " ",
        (text or "").lower(),
    )
    return re.sub(r"\s+", " ", clean).strip()


def highlight_search_key(text: str, word_limit: int = 5) -> str:
    return " ".join(normalize_for_match(text).split()[:word_limit])


def text_exists_in_content(highlight: str, content: str) -> bool:
    key = highlight_search_key(highlight, word_limit=5)
    if not key:
        return False
    hay = normalize_for_match(content)
    if key in hay:
        return True
    words = key.split()
    if len(words) >= 3:
        short_key = " ".join(words[:3])
        if short_key in hay:
            return True
    if len(words) >= 2 and words[0] in _CODE_HINTS:
        short_key = " ".join(words[:2])
        if short_key in hay:
            return True
    return False


def _quote_window(text: str, anchor_words: list[str], max_words: int = 8) -> str:
    """Фрагмент вокруг ключевых слов, а не только с начала строки."""
    words = text.split()
    if not words:
        return ""
    norm_words = [normalize_for_match(w) for w in words]
    anchor_idx = 0
    for i, nw in enumerate(norm_words):
        if any(a in nw or nw in a for a in anchor_words if a):
            anchor_idx = i
            break
    start = max(0, anchor_idx - 1)
    snippet = " ".join(words[start : start + max_words])
    return sanitize_highlight_text(snippet) or sanitize_highlight_text(" ".join(words[:max_words]))


def _quote_from_line(line: str, max_words: int = 8, anchor_words: list[str] | None = None) -> str:
    clean = re.sub(r"^#+\s*", "", line.strip())
    clean = re.sub(r"^\[Источник:[^\]]+\]\s*", "", clean)
    clean = re.sub(r"\*+", " ", clean).strip()
    if not clean:
        return ""
    if anchor_words:
        window = _quote_window(clean, anchor_words, max_words)
        if window:
            return window
    words = clean.split()
    min_words = (
        HIGHLIGHT_MIN_WORDS_CODE
        if any(w.lower().rstrip(":,") in _CODE_HINTS for w in words[:5])
        else HIGHLIGHT_MIN_WORDS
    )
    if len(words) < min_words:
        return ""
    snippet = " ".join(words[:max_words])
    if text_exists_in_content(snippet, clean):
        return snippet
    return sanitize_highlight_text(snippet)


def extract_highlight_quote(
    chunk_text: str,
    query: str | None = None,
    max_words: int = 8,
) -> str:
    """Короткая цитата из RAG-чанка; при query — фрагмент вокруг ключевых слов."""
    text = (chunk_text or "").strip()
    if not text:
        return ""

    lines = [
        ln.strip()
        for ln in text.split("\n")
        if ln.strip() and not ln.strip().startswith("[Источник:")
    ]
    query_words = [
        w
        for w in normalize_for_match(query or "").split()
        if (
            len(w) > 2
            or w in _CODE_HINTS
        )
        and w
        not in (
            "найди",
            "найти",
            "покажи",
            "где",
            "про",
            "этот",
            "эту",
            "циклы",
            "цикл",
        )
    ]

    if query_words:
        best_line = ""
        best_score = 0
        qnorm = normalize_for_match(query or "")
        wants_for_in = "for" in qnorm or "in" in qnorm or "цикл" in qnorm
        for line in lines:
            norm = normalize_for_match(line)
            score = sum(1 for w in query_words if w in norm)
            if wants_for_in and ("for-in" in norm or "for in" in norm):
                score += 3
            if score > best_score:
                best_score = score
                best_line = line
        if best_line and best_score > 0:
            quote = _quote_from_line(best_line, max_words, anchor_words=query_words)
            if quote:
                return quote

        for part in re.split(r"[.\n!?;]", text):
            part = part.strip()
            if len(part) < 8:
                continue
            norm = normalize_for_match(part)
            if any(w in norm for w in query_words):
                quote = _quote_from_line(part, max_words, anchor_words=query_words)
                if quote:
                    return quote

    for line in lines:
        if len(line) < 12:
            continue
        quote = _quote_from_line(line, max_words)
        if quote:
            return quote

    return sanitize_highlight_text(" ".join(text.split()[:max_words]))


def validate_highlight(highlight: str, page_content: str) -> dict:
    sanitized = sanitize_highlight_text(highlight)
    if not sanitized:
        return {
            "valid": False,
            "sanitized": "",
            "message": "Текст подсветки слишком короткий или содержит недопустимые символы",
        }
    if page_content and not text_exists_in_content(sanitized, page_content):
        return {
            "valid": False,
            "sanitized": sanitized,
            "message": "Фрагмент не найден на странице",
        }
    return {"valid": True, "sanitized": sanitized, "message": ""}
