from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.course import Course
from app.schemas.course import CourseResponse

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
