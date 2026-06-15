from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from enum import Enum

from app.schemas.homework_template import HomeworkTemplateContent

class HomeworkStatus(str, Enum):
    pending = "pending"
    submitted = "submitted"
    graded = "graded"

class HomeworkAssignmentBase(BaseModel):
    student_id: int

class HomeworkAssignmentCreate(HomeworkAssignmentBase):
    pass

class HomeworkAssignmentResponse(HomeworkAssignmentBase):
    id: int
    homework_id: int
    status: HomeworkStatus
    student_code: Optional[str] = None
    student_text: Optional[str] = None
    student_quiz: Optional[Dict[str, int]] = None
    teacher_feedback: Optional[str] = None
    grade: Optional[int] = None
    ai_review: Optional[Any] = None

    student_name: Optional[str] = None  # Helper field to return frontend

    class Config:
        from_attributes = True

class HomeworkBase(BaseModel):
    course_id: str
    title: str
    description: str
    ai_criteria: Optional[str] = None

class HomeworkCreate(HomeworkBase):
    student_ids: List[int]

class HomeworkResponse(HomeworkBase):
    id: int
    teacher_id: int
    assignments: List[HomeworkAssignmentResponse] = []
    content: Optional[HomeworkTemplateContent] = None
    is_demo: bool = False

    class Config:
        from_attributes = True

class HomeworkSubmit(BaseModel):
    student_code: str = ""
    student_text: str = ""
    student_quiz: Optional[Dict[str, int]] = None

class HomeworkGrade(BaseModel):
    teacher_feedback: str
    grade: int

class HomeworkAiReviewResponse(BaseModel):
    teacher_feedback: str
    suggested_grade: Optional[int] = None
    error_fragments: List[str] = []


class HomeworkHintRequest(BaseModel):
    student_code: Optional[str] = None
    student_text: Optional[str] = None
    student_quiz: Optional[dict] = None


class HomeworkHintResponse(BaseModel):
    hint: str


class HomeworkReminderItem(BaseModel):
    homework_id: int
    assignment_id: Optional[int] = None
    title: str
    course_id: str
    course_title: str = ""
    status: Optional[str] = None
    grade: Optional[int] = None


class HomeworkRemindersResponse(BaseModel):
    role: str
    message: str
    weak_topics: List[dict] = []
    adaptive_message: str = ""
    pending_count: Optional[int] = None
    waiting_count: Optional[int] = None
    pending_review_count: Optional[int] = None
    not_submitted_count: Optional[int] = None
    pending: List[HomeworkReminderItem] = []
    waiting: List[HomeworkReminderItem] = []
    pending_review: List[HomeworkReminderItem] = []
    not_submitted: List[HomeworkReminderItem] = []
    recent_grades: List[HomeworkReminderItem] = []


class JournalSummaryResponse(BaseModel):
    overall_avg: Optional[float] = None
    pending_review_count: int = 0
    not_submitted_count: int = 0
    courses: List[dict] = []
    students: List[dict] = []
    not_submitted: List[dict] = []
    pending_review: List[dict] = []
