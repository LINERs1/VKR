"""
Единый сервис навигации для голосового ИИ-ассистента.

Платформа передаёт список курсов в запросе (embeddable widget) или
ИИ подтягивает его с PLATFORM_SERVICE_URL.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import parse_qs, urlparse

STATIC_PATHS = frozenset({
    "/", "/profile", "/journal", "/homeworks", "/analytics", "/homeworks/workshop", "/admin",
})

# Специфичные ключи раньше; широкие (python) — в конце
COURSE_ALIAS_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("python-100-days-ru", ("100 дн", "сто дн", "сто дней", "за 100", "100 days")),
    ("react-30-days-ru", ("react", "реакт")),
    ("js-30-days-ru", ("javascript", "джаваскрипт", "js ")),
    ("ml", ("машинн", "machine learning", "ml ")),
    ("webdev", ("веб-разработ", "веб разработ", "webdev", "frontend")),
    ("sql", ("sql", "баз данных", "postgresql")),
    ("algorithms", ("алгоритм", "алгоритмизации")),
    ("python-100-days-ru", ("python", "питон", "пайтон")),
    ("python", ("python", "питон", "пайтон")),
]

_NUMBER_WORDS = {
    "сто": "100", "двести": "200", "триста": "300",
    "тысяча": "1000", "тыс": "1000",
    "один": "1", "два": "2", "три": "3", "четыре": "4", "пять": "5",
    "шесть": "6", "семь": "7", "восемь": "8", "девять": "9", "десять": "10",
}

_STT_REPLACEMENTS = (
    (r"\bпайтон\b", "python"),
    (r"\bпитон\b", "python"),
    (r"\bджава\s*скрипт\b", "javascript"),
    (r"\bреакт\b", "react"),
    (r"\bсто\s+дней\b", "100 дней"),
    (r"\bза\s+сто\b", "за 100"),
)


@dataclass
class CourseNavItem:
    id: str
    title: str = ""
    description: str = ""
    lessons: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CourseNavItem:
        lessons = raw.get("lessons") or []
        if not isinstance(lessons, list):
            lessons = []
        return cls(
            id=str(raw.get("id") or ""),
            title=str(raw.get("title") or ""),
            description=str(raw.get("description") or ""),
            lessons=lessons,
        )


@dataclass
class ResolveResult:
    status: str  # ok | ambiguous | not_found | static
    path: str | None = None
    course_id: str | None = None
    query: dict[str, str] = field(default_factory=dict)
    matches: list[dict[str, Any]] = field(default_factory=list)
    message: str = ""


def normalize_nav_path(raw: str | None) -> str | None:
    if raw is None:
        return None
    path = str(raw).strip()
    if not path:
        return None
    query = ""
    if "?" in path:
        base, q = path.split("?", 1)
        path, query = base, "?" + q
    low = path.lower().strip("/")
    if not low or low in ("home", "главная", "главную", "main"):
        return "/" + (query[1:] if query else "")
    if not path.startswith("/"):
        path = "/" + path
    path = path.rstrip("/") or "/"
    return path + query


def fuzzy_normalize_text(text: str) -> str:
    """Нормализация STT/речи для сопоставления с названиями курсов."""
    t = unicodedata.normalize("NFKC", (text or "").lower())
    t = t.replace("ё", "е")
    for pattern, repl in _STT_REPLACEMENTS:
        t = re.sub(pattern, repl, t, flags=re.IGNORECASE)
    for word, num in _NUMBER_WORDS.items():
        t = re.sub(rf"\b{word}\b", num, t)
    t = re.sub(r"[^\w\s\-./]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _split_path_query(path: str) -> tuple[str, dict[str, str]]:
    if "?" not in path:
        return path, {}
    base, qs = path.split("?", 1)
    parsed = parse_qs(qs, keep_blank_values=False)
    return base, {k: v[0] for k, v in parsed.items() if v}


def _course_slug_from_path(pathname: str) -> str | None:
    pathname = (pathname or "").strip()
    m = re.match(r"^/courses/(.+)$", pathname, re.I)
    if m:
        return m.group(1).lower().strip()
    bare = pathname.lstrip("/").lower().strip()
    if bare and "/" not in bare and bare not in ("profile", "journal", "homeworks", "analytics"):
        return bare
    return None


def _score_course(course: CourseNavItem, needle: str) -> float:
    if not needle:
        return 0.0
    nid = course.id.lower()
    title = course.title.lower()
    n = fuzzy_normalize_text(needle)
    fn = fuzzy_normalize_text(f"{course.title} {course.id}")

    if nid == n or n == nid:
        return 1.0
    if title and (n in title or title in n):
        return 0.92
    if nid in n or n in nid:
        return 0.88

    for alias_id, keys in COURSE_ALIAS_GROUPS:
        if alias_id != course.id:
            continue
        if any(k in n for k in keys):
            return 0.86

    ratio = SequenceMatcher(None, n, fn).ratio()
    if ratio >= 0.72:
        return ratio
    if title:
        tr = SequenceMatcher(None, n, title).ratio()
        if tr >= 0.65:
            return tr * 0.95
    return 0.0


def _rank_courses(courses: list[CourseNavItem], needle: str) -> list[tuple[float, CourseNavItem]]:
    scored = [( _score_course(c, needle), c) for c in courses if c.id]
    scored = [(s, c) for s, c in scored if s >= 0.55]
    scored.sort(key=lambda x: (-x[0], -(len(x[1].title or ""))))
    return scored


def resolve_path_or_query(
    path_or_query: str,
    courses: list[CourseNavItem],
    *,
    custom_paths: set[str] = None,
    ambiguity_gap: float = 0.08,
) -> ResolveResult:
    raw = (path_or_query or "").strip()
    if not raw:
        return ResolveResult(status="not_found", message="Пустой путь")

    normalized = normalize_nav_path(raw)
    if not normalized:
        return ResolveResult(status="not_found", message="Некорректный путь")

    pathname, query = _split_path_query(normalized)

    all_paths = STATIC_PATHS | (custom_paths or set())
    if pathname in all_paths:
        return ResolveResult(status="static", path=pathname + (_query_suffix(query)), query=query)
    if pathname.startswith("/homeworks/") or pathname.startswith("/journal/"):
        return ResolveResult(status="static", path=pathname + (_query_suffix(query)), query=query)

    if not courses:
        return ResolveResult(status="not_found", message="Список курсов пуст")

    slug = _course_slug_from_path(pathname)
    needle = slug if slug else fuzzy_normalize_text(raw)

    ranked = _rank_courses(courses, needle)
    if not ranked:
        return ResolveResult(
            status="not_found",
            message=f"Курс не найден: {raw}",
        )

    top_score, top = ranked[0]
    if len(ranked) > 1 and (top_score - ranked[1][0]) < ambiguity_gap:
        matches = [
            {"id": c.id, "title": c.title, "score": round(s, 2)}
            for s, c in ranked[:5]
        ]
        return ResolveResult(
            status="ambiguous",
            matches=matches,
            message="Найдено несколько подходящих курсов",
        )

    path = f"/courses/{top.id}" + (_query_suffix(query))
    return ResolveResult(
        status="ok",
        path=path,
        course_id=top.id,
        query=query,
        message="OK",
    )


def _query_suffix(query: dict[str, str]) -> str:
    if not query:
        return ""
    from urllib.parse import urlencode
    return "?" + urlencode(query)


def validate_navigate_path(path: str, courses: list[CourseNavItem], custom_paths: set[str] = None) -> ResolveResult:
    """Проверка пути из [NAVIGATE:...] перед отправкой на виджет."""
    res = resolve_path_or_query(path, courses, custom_paths=custom_paths)
    if res.status == "not_found":
        return res
    if res.status == "ambiguous":
        return ResolveResult(
            status="ambiguous",
            path=None,
            matches=res.matches,
            message=res.message,
        )
    return res


def resolve_adjacent_lesson(
    course_id: str,
    current_lesson_index: int,
    delta: int,
    courses: list[CourseNavItem],
) -> ResolveResult:
    course = next((c for c in courses if c.id == course_id), None)
    if not course:
        ranked = _rank_courses(courses, course_id)
        if ranked:
            course = ranked[0][1]
    if not course:
        return ResolveResult(status="not_found", message=f"Курс «{course_id}» не найден")

    lessons = course.lessons or []
    total = len(lessons)
    if total == 0:
        return ResolveResult(status="not_found", message="В курсе нет уроков")

    cur = int(current_lesson_index or 1)
    target = cur + int(delta)
    if target < 1 or target > total:
        edge = "первый" if delta < 0 else "последний"
        return ResolveResult(
            status="not_found",
            message=f"Это уже {edge} урок курса ({cur} из {total})",
        )

    lesson = lessons[target - 1]
    title = lesson.get("title") or f"Урок {target}"
    lesson_db_id = lesson.get("id")
    query = {"lesson_idx": str(target)}
    if lesson_db_id is not None:
        query["lesson"] = str(lesson_db_id)

    path = f"/courses/{course.id}" + _query_suffix(query)

    return ResolveResult(
        status="ok",
        path=path,
        course_id=course.id,
        query=query,
        matches=[{"lesson_index": target, "lesson_title": title, "lesson_id": lesson_db_id}],
        message=f"Урок {target}: {title}",
    )


def build_breadcrumbs_text(breadcrumbs: list[dict[str, Any]] | None) -> str:
    if not breadcrumbs:
        return ""
    parts = [str(b.get("label") or b.get("title") or "?") for b in breadcrumbs]
    return " → ".join(parts)
