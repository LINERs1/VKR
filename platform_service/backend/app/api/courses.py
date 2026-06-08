from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.course import Course
from app.schemas.course import CourseResponse, CourseCreate
import requests
import os
import logging
from app.api.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8000")

router = APIRouter()

@router.get("/courses", response_model=List[CourseResponse])
async def get_courses(db: Session = Depends(get_db)):
    courses = db.query(Course).all()
    # Pydantic will handle parsing tags string to list in schema if we configure it, or we do it here.
    # Actually our schema expects List[str] but DB returns str. We need to handle this.
    result = []
    for c in courses:
        c_dict = {
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "icon": c.icon,
            "color": c.color,
            "tags": [t.strip() for t in c.tags.split(",") if t.strip()] if c.tags else [],
            "lessons_count": c.lessons_count,
            "duration": c.duration,
            "students": c.students,
            "rating": c.rating,
            "instructor": c.instructor,
            "lessons": c.lessons
        }
        result.append(c_dict)
    return result

@router.post("/courses", response_model=CourseResponse)
async def create_course(
    course_in: CourseCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create courses")

    # Check if course exists
    existing = db.query(Course).filter(Course.id == course_in.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Course ID already exists")

    course = Course(
        id=course_in.id,
        title=course_in.title,
        description=course_in.description,
        icon=course_in.icon,
        color=course_in.color,
        tags=course_in.tags,
        duration=course_in.duration,
        instructor=course_in.instructor,
        lessons_count=0,
        students=0,
        rating=0.0
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    # Send webhook to AI service
    payload = {
        "id": course.id,
        "title": course.title
    }
    try:
        requests.post(f"{AI_SERVICE_URL}/webhook/course", json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send webhook to AI service: {e}")

    c_dict = {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "icon": course.icon,
        "color": course.color,
        "tags": [t.strip() for t in course.tags.split(",") if t.strip()] if course.tags else [],
        "lessons_count": course.lessons_count,
        "duration": course.duration,
        "students": course.students,
        "rating": course.rating,
        "instructor": course.instructor,
        "lessons": []
    }
    return c_dict

@router.get("/courses/{course_id}", response_model=CourseResponse)
async def get_course(course_id: str, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    c_dict = {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "icon": course.icon,
        "color": course.color,
        "tags": [t.strip() for t in course.tags.split(",") if t.strip()] if course.tags else [],
        "lessons_count": course.lessons_count,
        "duration": course.duration,
        "students": course.students,
        "rating": course.rating,
        "instructor": course.instructor,
        "lessons": course.lessons
    }
    return c_dict
