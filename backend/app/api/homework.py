from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.homework import Homework, HomeworkAssignment, HomeworkStatus
from app.models.user import User, UserRole
from app.schemas.homework import (
    HomeworkCreate, HomeworkResponse, HomeworkSubmit, HomeworkGrade, HomeworkAssignmentResponse
)
from app.services.auth_service import get_current_user

router = APIRouter()

@router.post("/", response_model=HomeworkResponse)
def create_homework(
    hw_in: HomeworkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.teacher.value:
        raise HTTPException(status_code=403, detail="Only teachers can create homeworks")
    
    # Verify students exist
    students = db.query(User).filter(User.id.in_(hw_in.student_ids), User.role == UserRole.student.value).all()
    if len(students) != len(hw_in.student_ids):
        raise HTTPException(status_code=400, detail="One or more students not found or invalid role")

    homework = Homework(
        course_id=hw_in.course_id,
        teacher_id=current_user.id,
        title=hw_in.title,
        description=hw_in.description
    )
    db.add(homework)
    db.flush()

    for student_id in hw_in.student_ids:
        assignment = HomeworkAssignment(
            homework_id=homework.id,
            student_id=student_id,
            status=HomeworkStatus.pending.value
        )
        db.add(assignment)
    
    db.commit()
    db.refresh(homework)
    
    # Populate student_names for response
    for a in homework.assignments:
        a.student_name = a.student.username
        
    return homework

@router.get("/", response_model=list[HomeworkResponse])
def get_homeworks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == UserRole.teacher.value:
        homeworks = db.query(Homework).filter(Homework.teacher_id == current_user.id).all()
    else:
        assignments = db.query(HomeworkAssignment).filter(HomeworkAssignment.student_id == current_user.id).all()
        # Return homeworks where student has an assignment
        homeworks = [a.homework for a in assignments]
    
    # Attach student names
    for hw in homeworks:
        for a in hw.assignments:
            a.student_name = a.student.username
            
    return homeworks

@router.get("/{homework_id}", response_model=HomeworkResponse)
def get_homework(homework_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    homework = db.query(Homework).filter(Homework.id == homework_id).first()
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
        
    # Access control
    if current_user.role == UserRole.student.value:
        assignment = next((a for a in homework.assignments if a.student_id == current_user.id), None)
        if not assignment:
            raise HTTPException(status_code=403, detail="Not assigned to you")
    elif current_user.role == UserRole.teacher.value:
        if homework.teacher_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your homework")

    for a in homework.assignments:
        a.student_name = a.student.username
    return homework

@router.put("/assignments/{assignment_id}/submit", response_model=HomeworkAssignmentResponse)
def submit_homework(
    assignment_id: int,
    submission: HomeworkSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.student.value:
        raise HTTPException(status_code=403, detail="Only students can submit homework")
        
    assignment = db.query(HomeworkAssignment).filter(HomeworkAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    if assignment.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your assignment")
        
    assignment.student_code = submission.student_code
    assignment.student_text = submission.student_text
    assignment.status = HomeworkStatus.submitted.value
    
    db.commit()
    db.refresh(assignment)
    assignment.student_name = assignment.student.username
    return assignment

@router.put("/assignments/{assignment_id}/grade", response_model=HomeworkAssignmentResponse)
def grade_homework(
    assignment_id: int,
    grading: HomeworkGrade,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.teacher.value:
        raise HTTPException(status_code=403, detail="Only teachers can grade homework")
        
    assignment = db.query(HomeworkAssignment).filter(HomeworkAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    if assignment.homework.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your assignment to grade")
        
    assignment.teacher_feedback = grading.teacher_feedback
    assignment.grade = grading.grade
    assignment.status = HomeworkStatus.graded.value
    
    db.commit()
    db.refresh(assignment)
    assignment.student_name = assignment.student.username
    return assignment
