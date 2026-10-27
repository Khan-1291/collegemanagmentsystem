"""
Quizzes Router for Government Post Graduate College Mardan (GPGCM)
Computer Science Department Management System (Phase 1)
Affiliated with Abdul Wali Khan University Mardan (AWKUM)

Handles:
- Faculty scheduling quizzes (max 5 marks for AWKUM internal criteria)
- Listing quizzes by subject
- Bulk entry and updating of student quiz scores
- Student personal quiz marks view
"""

import html
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from app.core.academic import (
    get_allocated_sections,
    require_subject_department_access,
    require_enrolled_students,
    require_faculty_subject_allocation,
    require_student_subject_enrollment,
)
from app.database import get_db
from app.models.models import (
    User,
    UserRole,
    Quiz,
    QuizMarks,
    Subject,
    FacultyProfile,
    FacultySubject,
    StudentProfile
)
from app.schemas.schemas import (
    QuizCreate,
    QuizOut,
    QuizMarksBulkCreate,
    QuizMarksOut
)
from app.core.deps import (
    get_current_user,
    require_faculty_or_admin,
    get_current_student_profile
)
from app.services.email_service import queue_email
from app.services.notifications import enrolled_student_emails, notify_student

router = APIRouter(prefix="/quizzes", tags=["Quizzes Management"])


# ============================================================================
# 1. Faculty Creates a Quiz (Max 5 Marks)
# ============================================================================
@router.post(
    "/",
    response_model=QuizOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Quiz (Faculty / Admin)"
)
def create_quiz(
    payload: QuizCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Creates a new quiz for a subject.
    Maximum marks is constrained to 5.0 as per AWKUM / GPGCM internal criteria.
    
    Restricted to: Faculty, HOD, and Super Admin.
    """
    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {payload.subject_id} not found."
        )
    require_subject_department_access(db, current_user, payload.subject_id)

    # Determine faculty_id
    faculty_id = None
    if current_user.role == UserRole.FACULTY:
        faculty = require_faculty_subject_allocation(
            db, current_user, payload.subject_id, payload.academic_session.strip()
        )
        if not faculty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Faculty profile not found for this user."
            )
        faculty_id = faculty.id
    else:
        first_fac = db.query(FacultyProfile).first()
        faculty_id = first_fac.id if first_fac else 1

    quiz = Quiz(
        subject_id=payload.subject_id,
        faculty_id=faculty_id,
        academic_session=payload.academic_session.strip(),
        title=payload.title.strip(),
        description=payload.description,
        max_marks=payload.max_marks,
        quiz_date=payload.quiz_date
    )
    recipients = enrolled_student_emails(
        db,
        payload.subject_id,
        payload.academic_session.strip(),
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    for _, email, full_name in recipients:
        queue_email(
            background_tasks,
            email,
            f"New quiz scheduled: {quiz.title}",
            "A new quiz has been scheduled",
            [
                f"Dear {html.escape(full_name)},",
                f"<strong>{html.escape(quiz.title)}</strong> is scheduled for "
                f"{html.escape(subject.code)} · {html.escape(payload.academic_session.strip())}.",
                f"Quiz date: {html.escape(quiz.quiz_date.strftime('%B %d, %Y'))}. "
                f"Maximum marks: {quiz.max_marks:g}.",
                html.escape(quiz.description or "Sign in to the college portal for more details."),
            ],
        )
    return quiz


# ============================================================================
# 2. List Quizzes for a Subject
# ============================================================================
@router.get(
    "/subject/{subject_id}",
    response_model=List[QuizOut],
    summary="List Quizzes for a Subject"
)
def get_subject_quizzes(
    subject_id: int,
    academic_session: Optional[str] = Query(None, description="e.g. Fall 2024"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves all quizzes conducted or scheduled for a subject.
    Accessible to all authenticated users (Faculty and Students).
    """
    query = db.query(Quiz).filter(Quiz.subject_id == subject_id)
    if academic_session:
        require_student_subject_enrollment(
            db, current_user, subject_id, academic_session
        )
        require_faculty_subject_allocation(db, current_user, subject_id, academic_session)
        query = query.filter(Quiz.academic_session == academic_session)
    else:
        if current_user.role == UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Academic session is required to view enrolled course work."
            )
        require_faculty_subject_allocation(db, current_user, subject_id)
        if current_user.role == UserRole.FACULTY:
            faculty = db.query(FacultyProfile).filter(
                FacultyProfile.user_id == current_user.id
            ).first()
            sessions = db.query(FacultySubject.academic_session).filter(
                FacultySubject.faculty_id == faculty.id,
                FacultySubject.subject_id == subject_id,
            )
            query = query.filter(Quiz.academic_session.in_(sessions))

    return query.order_by(Quiz.quiz_date.desc()).all()


@router.get(
    "/{quiz_id}/marks",
    response_model=List[QuizMarksOut],
    summary="List Quiz Marks for the Enrolled Class"
)
def get_quiz_marks(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if quiz is None:
        raise HTTPException(status_code=404, detail=f"Quiz with ID {quiz_id} not found.")
    require_faculty_subject_allocation(
        db, current_user, quiz.subject_id, quiz.academic_session
    )
    query = (
        db.query(QuizMarks)
        .filter(QuizMarks.quiz_id == quiz_id)
        .options(joinedload(QuizMarks.student).joinedload(StudentProfile.user))
    )
    sections = get_allocated_sections(
        db, current_user, quiz.subject_id, quiz.academic_session
    )
    if sections is not None:
        query = (
            query.join(StudentProfile, QuizMarks.student_id == StudentProfile.id)
            .filter(StudentProfile.section.in_(sections))
        )
    return query.all()


# ============================================================================
# 3. Faculty Enters Quiz Marks for Multiple Students
# ============================================================================
@router.post(
    "/{quiz_id}/marks/bulk",
    response_model=List[QuizMarksOut],
    status_code=status.HTTP_200_OK,
    summary="Bulk Enter Quiz Marks (Faculty / Admin)"
)
def enter_quiz_marks_bulk(
    quiz_id: int,
    payload: QuizMarksBulkCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Enters or updates quiz marks for multiple students in a single request.
    Validates that obtained marks do not exceed the quiz's max_marks (5.0).
    
    Restricted to: Faculty, HOD, and Super Admin.
    """
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quiz with ID {quiz_id} not found."
        )

    require_faculty_subject_allocation(
        db, current_user, quiz.subject_id, quiz.academic_session
    )
    require_enrolled_students(
        db,
        current_user,
        quiz.subject_id,
        quiz.academic_session,
        {item.student_id for item in payload.marks},
    )

    saved_marks = []
    for item in payload.marks:
        if item.obtained_marks < 0.0 or item.obtained_marks > quiz.max_marks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Obtained marks ({item.obtained_marks}) for student {item.student_id} must be between 0.0 and {quiz.max_marks}."
            )

        existing = (
            db.query(QuizMarks)
            .filter(
                QuizMarks.quiz_id == quiz_id,
                QuizMarks.student_id == item.student_id
            )
            .first()
        )

        if existing:
            existing.obtained_marks = item.obtained_marks
            existing.remarks = item.remarks
            saved_marks.append(existing)
        else:
            record = QuizMarks(
                quiz_id=quiz_id,
                student_id=item.student_id,
                obtained_marks=item.obtained_marks,
                remarks=item.remarks
            )
            db.add(record)
            saved_marks.append(record)

    db.commit()
    for s in saved_marks:
        db.refresh(s)

    for item in payload.marks:
        notify_student(
            background_tasks,
            db,
            item.student_id,
            f"Quiz marks posted: {quiz.title}",
            "Your quiz marks are available",
            [
                f"<strong>{html.escape(quiz.title)}</strong>: "
                f"{item.obtained_marks:g} / {quiz.max_marks:g} marks.",
                f"Subject: {html.escape(quiz.subject.code if quiz.subject else str(quiz.subject_id))} · "
                f"{html.escape(quiz.academic_session)}.",
            ],
        )
    return saved_marks


# ============================================================================
# 4. Student Views Their Own Quiz Marks
# ============================================================================
@router.get(
    "/my-marks",
    summary="Student Personal Quiz Scores"
)
def get_my_quiz_marks(
    academic_session: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    student: StudentProfile = Depends(get_current_student_profile)
):
    """
    Returns all quizzes and corresponding marks obtained by the authenticated student.
    Restricted to: Authenticated Students.
    """
    query = (
        db.query(QuizMarks)
        .join(Quiz, QuizMarks.quiz_id == Quiz.id)
        .filter(QuizMarks.student_id == student.id)
        .options(joinedload(QuizMarks.quiz).joinedload(Quiz.subject))
    )

    if academic_session:
        query = query.filter(Quiz.academic_session == academic_session)

    records = query.order_by(Quiz.quiz_date.desc()).all()

    return [
        {
            "quiz_id": r.quiz.id,
            "title": r.quiz.title,
            "description": r.quiz.description,
            "subject_id": r.quiz.subject_id,
            "subject_code": r.quiz.subject.code if r.quiz.subject else "N/A",
            "subject_title": r.quiz.subject.title if r.quiz.subject else "N/A",
            "quiz_date": r.quiz.quiz_date.isoformat(),
            "max_marks": r.quiz.max_marks,
            "obtained_marks": r.obtained_marks,
            "remarks": r.remarks
        }
        for r in records
    ]
