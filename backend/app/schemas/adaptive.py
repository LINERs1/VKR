from typing import List, Optional

from pydantic import BaseModel


class WeakTopicItem(BaseModel):
    topic: str
    wrong_count: int
    course_id: str
    course_title: str = ""
    lesson_id: Optional[int] = None
    lesson_title: Optional[str] = None
    last_wrong_at: Optional[str] = None


class WeakTopicsResponse(BaseModel):
    items: List[WeakTopicItem] = []
    message: str = ""


class ChatHistoryMessage(BaseModel):
    role: str
    content: str


class AnalyticsEventIn(BaseModel):
    event_type: str
    course_id: Optional[str] = None
    duration_ms: Optional[float] = None
    success: bool = True
    meta: dict = {}


class MetricStats(BaseModel):
    count: int = 0
    avg_ms: Optional[float] = None
    min_ms: Optional[float] = None
    max_ms: Optional[float] = None


class AnalyticsSummaryResponse(BaseModel):
    period_days: int
    total_events: int
    chat_rag: MetricStats
    chat_llm: MetricStats
    ai_homework_review: MetricStats
    homework_hint: MetricStats
    voice_navigation: dict


class DetailedAnalyticsResponse(BaseModel):
    period_days: int
    summary: dict
    daily_events: list
    perf_by_day: list
    homework: dict
    hw_by_day: list
    student_activity: list
    weak_topics: list
