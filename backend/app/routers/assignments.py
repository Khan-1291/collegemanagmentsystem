"""
Assignments Router for Government Post Graduate College Mardan (GPGCM)
Computer Science Department Management System (Phase 1)
Affiliated with Abdul Wali Khan University Mardan (AWKUM)

Handles:
- Faculty creating assignments (max 5 marks for AWKUM internal criteria)
- Listing assignments by subject
- Student file upload submissions (PDF, DOCX, ZIP, PY, etc.)
- Faculty grading with marks and feedback
- Student personal submissions view
"""

import os
import html
import shutil
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Query
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.core.academic import (
    get_allocated_sections,
    require_subject_department_access,
    require_enrolled_students,
    require_faculty_subject_allocation,
    require_student_subject_enrollment,
)
from app.config import settings
from app.database import get_db
from app.models.models import (
    User,
    UserRole,
    Assignment,
    AssignmentSubmission,
    Subject,
    FacultyProfile,
    StudentProfile,
    FacultySubject,
)
from app.schemas.schemas import (
    AssignmentCreate,
    AssignmentOut,
    AssignmentSubmissionOut,
    AssignmentSubmissionGrade,
    MessageResponse
)
from app.core.deps import (
    get_current_user,
    require_faculty_or_admin,
    get_current_student_profile
)
from app.services.email_service import queue_email
from app.services.notifications import enrolled_student_emails, notify_student

router = APIRouter(prefix="/assignments", tags=["Assignments Management"])


# ============================================================================
# 1. Faculty Creates an Assignment (Max 5 Marks)
# ============================================================================
@router.post(
    "/",
    response_model=AssignmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Assignment (Faculty / Admin)"
)
def create_assignment(
    payload: AssignmentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Creates a new assignment for a subject.
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
        fac = require_faculty_subject_allocation(
            db, current_user, payload.subject_id, payload.academic_session.strip()
        )
        if not fac:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Faculty profile not found for this user."
            )
        faculty_id = fac.id
    else:
        first_fac = db.query(FacultyProfile).first()
        faculty_id = first_fac.id if first_fac else 1

    assignment = Assignment(
        subject_id=payload.subject_id,
        faculty_id=faculty_id,
        academic_session=payload.academic_session.strip(),
        title=payload.title.strip(),
        description=payload.description,
        max_marks=payload.max_marks,
        due_date=payload.due_date
    )
    recipients = enrolled_student_emails(
        db,
        payload.subject_id,
        payload.academic_session.strip(),
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    for _, email, full_name in recipients:
        queue_email(
            background_tasks,
            email,
            f"New assignment: {assignment.title}",
            "A new assignment is available",
            [
                f"Dear {html.escape(full_name)},",
                f"<strong>{html.escape(assignment.title)}</strong> has been posted for "
                f"{html.escape(subject.code)} · {html.escape(payload.academic_session.strip())}.",
                f"Due date: {html.escape(assignment.due_date.strftime('%B %d, %Y at %I:%M %p'))}.",
                html.escape(assignment.description or "Sign in to the college portal to view the assignment details."),
            ],
        )
    assignment.submissions_count = 0
    return assignment


# ============================================================================
# 2. List Assignments of a Subject
# ============================================================================
@router.get(
    "/subject/{subject_id}",
    response_model=List[AssignmentOut],
    summary="List Assignments for a Subject"
)
def get_subject_assignments(
    subject_id: int,
    academic_session: Optional[str] = Query(None, description="e.g. Fall 2024"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves all assignments published for a specific subject.
    Accessible to all authenticated users (Faculty and Students).
    """
    query = db.query(Assignment).filter(Assignment.subject_id == subject_id)
    if academic_session:
        require_student_subject_enrollment(
            db, current_user, subject_id, academic_session
        )
        require_faculty_subject_allocation(db, current_user, subject_id, academic_session)
        query = query.filter(Assignment.academic_session == academic_session)
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
            query = query.filter(Assignment.academic_session.in_(sessions))

    assignments = query.order_by(Assignment.created_at.desc()).all()

    for a in assignments:
        a.submissions_count = (
            db.query(AssignmentSubmission)
            .filter(AssignmentSubmission.assignment_id == a.id)
            .count()
        )

    return assignments


@router.get(
    "/{assignment_id}/submissions",
    response_model=List[AssignmentSubmissionOut],
    summary="List Assignment Submissions for Grading"
)
def get_assignment_submissions(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if assignment is None:
        raise HTTPException(status_code=404, detail=f"Assignment with ID {assignment_id} not found.")
    require_faculty_subject_allocation(
        db, current_user, assignment.subject_id, assignment.academic_session
    )
    query = (
        db.query(AssignmentSubmission)
        .filter(AssignmentSubmission.assignment_id == assignment_id)
        .options(joinedload(AssignmentSubmission.student).joinedload(StudentProfile.user))
        .order_by(AssignmentSubmission.submitted_at.asc())
    )
    sections = get_allocated_sections(
        db, current_user, assignment.subject_id, assignment.academic_session
    )
    if sections is not None:
        query = (
            query.join(StudentProfile, AssignmentSubmission.student_id == StudentProfile.id)
            .filter(StudentProfile.section.in_(sections))
        )
    return query.all()


# ============================================================================
# 3. Student Submits File for an Assignment
# ============================================================================
@router.post(
    "/{assignment_id}/submit",
    response_model=AssignmentSubmissionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Student Uploads Assignment File"
)
async def submit_assignment_file(
    assignment_id: int,
    file: UploadFile = File(..., description="Assignment document (PDF, DOCX, ZIP, etc.)"),
    db: Session = Depends(get_db),
    student: StudentProfile = Depends(get_current_student_profile),
    current_user: User = Depends(get_current_user),
):
    """
    Allows an enrolled student to upload their assignment submission file.
    Validates file extension and securely saves the file.
    
    Restricted to: Authenticated Students.
    """
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment with ID {assignment_id} not found."
        )
    require_student_subject_enrollment(
        db, current_user, assignment.subject_id, assignment.academic_session
    )

    # Validate file extension
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    # Save to storage directory
    submission_dir = os.path.join(settings.UPLOAD_DIR, "submissions")
    os.makedirs(submission_dir, exist_ok=True)
    clean_filename = f"assign_{assignment_id}_std_{student.id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(submission_dir, clean_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Check for existing submission
    existing = (
        db.query(AssignmentSubmission)
        .filter(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id == student.id
        )
        .first()
    )

    if existing:
        # Update existing submission
        existing.file_path = file_path
        existing.original_filename = file.filename
        existing.submitted_at = datetime.utcnow()
        existing.obtained_marks = None  # Reset previous grade upon resubmission
        existing.feedback = None
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new submission
        submission = AssignmentSubmission(
            assignment_id=assignment_id,
            student_id=student.id,
            file_path=file_path,
            original_filename=file.filename,
            submitted_at=datetime.utcnow()
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        return submission


# ============================================================================
# 4. Faculty Grades an Assignment Submission
# ============================================================================
@router.post(
    "/submissions/{submission_id}/grade",
    response_model=AssignmentSubmissionOut,
    status_code=status.HTTP_200_OK,
    summary="Grade Assignment Submission (Faculty / Admin)"
)
def grade_submission(
    submission_id: int,
    payload: AssignmentSubmissionGrade,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Allows faculty to evaluate a student submission, award marks (0 to 5),
    and provide qualitative feedback.
    
    Restricted to: Faculty, HOD, and Super Admin.
    """
    submission = (
        db.query(AssignmentSubmission)
        .filter(AssignmentSubmission.id == submission_id)
        .options(joinedload(AssignmentSubmission.assignment))
        .first()
    )
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission with ID {submission_id} not found."
        )

    require_faculty_subject_allocation(
        db,
        current_user,
        submission.assignment.subject_id,
        submission.assignment.academic_session,
    )
    require_enrolled_students(
        db,
        current_user,
        submission.assignment.subject_id,
        submission.assignment.academic_session,
        {submission.student_id},
    )

    if payload.obtained_marks < 0.0 or payload.obtained_marks > submission.assignment.max_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Obtained marks ({payload.obtained_marks}) must be between 0.0 and max marks ({submission.assignment.max_marks})."
        )

    faculty = db.query(FacultyProfile).filter(FacultyProfile.user_id == current_user.id).first()
    faculty_id = faculty.id if faculty else None

    submission.obtained_marks = payload.obtained_marks
    submission.feedback = payload.feedback
    submission.graded_by = faculty_id
    submission.graded_at = datetime.utcnow()

    db.commit()
    db.refresh(submission)
    notify_student(
        background_tasks,
        db,
        submission.student_id,
        f"Assignment grade posted: {submission.assignment.title}",
        "Your assignment has been graded",
        [
            f"<strong>{html.escape(submission.assignment.title)}</strong>: "
            f"{submission.obtained_marks:g} / {submission.assignment.max_marks:g} marks.",
            f"Feedback: {html.escape(submission.feedback or 'No additional feedback was provided.')}",
        ],
    )
    return submission


# ============================================================================
# 5. Student Views Their Own Submissions
# ============================================================================
@router.get(
    "/my-submissions",
    response_model=List[AssignmentSubmissionOut],
    summary="Student Personal Submissions & Grades"
)
def get_my_submissions(
    db: Session = Depends(get_db),
    student: StudentProfile = Depends(get_current_student_profile)
):
    """
    Returns all assignment submissions, grades, and teacher feedback
    for the authenticated student.
    
    Restricted to: Authenticated Students.
    """
    submissions = (
        db.query(AssignmentSubmission)
        .filter(AssignmentSubmission.student_id == student.id)
        .options(
            joinedload(AssignmentSubmission.assignment),
            joinedload(AssignmentSubmission.student).joinedload(StudentProfile.user)
        )
        .order_by(AssignmentSubmission.submitted_at.desc())
        .all()
    )
    return submissions
