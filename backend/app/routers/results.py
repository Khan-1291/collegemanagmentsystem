"""
Internal Results Router for Government Post Graduate College Mardan (GPGCM)
Computer Science Department Management System (Phase 1)
Affiliated with Abdul Wali Khan University Mardan (AWKUM)

Calculates the official 40-Mark Internal Evaluation Formula:
1. Mid-Term Examination : 20 Marks
2. Graded Assignments   : 05 Marks
3. Scheduled Quizzes    : 05 Marks
4. Topic Presentation   : 05 Marks
5. Attendance (Slab)    : 05 Marks
-----------------------------------------
Total Internal Result   : 40 Marks
"""

import html
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from app.core.academic import (
    get_allocated_sections,
    require_faculty_subject_allocation,
    require_subject_department_access,
)
from app.database import get_db
from app.models.models import (
    User,
    UserRole,
    InternalResult,
    Subject,
    StudentProfile,
    StudentSubject,
    EnrollmentStatus,
)
from app.schemas.schemas import (
    InternalResultOut,
    InternalResultCalculateRequest,
    FinalizeResultRequest,
    MessageResponse
)
from app.services.marks_calculator import (
    calculate_subject_internal_results,
    calculate_student_internal_result
)
from app.core.deps import (
    get_current_user,
    require_faculty_or_admin,
    require_hod_or_admin,
    get_current_student_profile
)
from app.services.notifications import notify_student

router = APIRouter(prefix="/results", tags=["Internal Results (Total 40 Marks)"])


# ============================================================================
# 1. Calculate Internal Results for All Enrolled Students in a Subject
# ============================================================================
@router.post(
    "/calculate",
    response_model=List[InternalResultOut],
    status_code=status.HTTP_200_OK,
    summary="Auto-Calculate Internal Results for All Enrolled Students"
)
def calculate_results(
    payload: InternalResultCalculateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Triggers the calculation of the official 40-mark internal evaluation for all students
    enrolled in the specified subject for the given academic session.
    
    Formula applied:
    - Mid Paper (Max: 20)
    - Assignments (Max: 5)
    - Quizzes (Max: 5)
    - Presentation (Max: 5)
    - Attendance Marks (Max: 5, based on exact AWKUM percentage slabs)
    Total Internal = 40 Marks
    
    Restricted to: Faculty teaching the course, HOD, and Super Admin.
    """
    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {payload.subject_id} not found."
        )

    sections = get_allocated_sections(
        db, current_user, payload.subject_id, payload.academic_session
    )
    if payload.section:
        require_faculty_subject_allocation(
            db, current_user, payload.subject_id, payload.academic_session, payload.section
        )
        sections = {payload.section.strip().upper()} if sections is not None else None

    # Check if there are enrolled students
    enrollment_query = (
        db.query(StudentSubject)
        .filter(
            StudentSubject.subject_id == payload.subject_id,
            StudentSubject.academic_session == payload.academic_session.strip(),
            StudentSubject.status == EnrollmentStatus.ENROLLED,
        )
    )
    if sections is not None:
        enrollment_query = (
            enrollment_query
            .join(StudentProfile, StudentSubject.student_id == StudentProfile.id)
            .filter(StudentProfile.section.in_(sections))
        )
    enrollments_count = enrollment_query.count()

    if enrollments_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No students enrolled in subject '{subject.code}' for academic session '{payload.academic_session}'."
        )

    # Perform calculation via marks_calculator service
    calculate_subject_internal_results(
        db=db,
        subject_id=payload.subject_id,
        academic_session=payload.academic_session.strip(),
        sections=sections,
    )

    # Return refreshed results with loaded relations
    result_query = (
        db.query(InternalResult)
        .filter(
            InternalResult.subject_id == payload.subject_id,
            InternalResult.academic_session == payload.academic_session.strip()
        )
        .options(
            joinedload(InternalResult.student).joinedload(StudentProfile.user),
            joinedload(InternalResult.subject)
        )
        .order_by(InternalResult.id.asc())
    )
    if sections is not None:
        result_query = (
            result_query
            .join(StudentProfile, InternalResult.student_id == StudentProfile.id)
            .filter(StudentProfile.section.in_(sections))
        )
    calculated_results = result_query.all()

    for result in calculated_results:
        notify_student(
            background_tasks,
            db,
            result.student_id,
            f"Internal result calculated: {subject.code}",
            "Your internal result is available",
            [
                f"<strong>{html.escape(subject.code)}</strong> · "
                f"{html.escape(payload.academic_session)}: "
                f"{result.total_internal:g} / 40 marks.",
            ],
        )
    return calculated_results


# ============================================================================
# 2. Get Official Internal Award List for a Subject
# ============================================================================
@router.get(
    "/subject/{subject_id}",
    response_model=List[InternalResultOut],
    summary="Get Official Internal Award List of a Subject"
)
def get_subject_award_list(
    subject_id: int,
    academic_session: str = Query(..., description="e.g. Fall 2024 or Spring 2025"),
    section: Optional[str] = Query(None, max_length=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Retrieves the complete internal evaluation award list (all students) for the subject.
    If results have not been calculated yet, they are automatically computed and returned.
    
    Restricted to: Faculty, HOD, and Super Admin.
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} not found."
        )

    sections = get_allocated_sections(db, current_user, subject_id, academic_session)
    if section:
        require_faculty_subject_allocation(db, current_user, subject_id, academic_session, section)
        sections = {section.strip().upper()} if sections is not None else None

    result_query = (
        db.query(InternalResult)
        .filter(
            InternalResult.subject_id == subject_id,
            InternalResult.academic_session == academic_session.strip()
        )
        .options(
            joinedload(InternalResult.student).joinedload(StudentProfile.user),
            joinedload(InternalResult.subject)
        )
    )
    if sections is not None:
        result_query = (
            result_query
            .join(StudentProfile, InternalResult.student_id == StudentProfile.id)
            .filter(StudentProfile.section.in_(sections))
        )
    results = result_query.all()

    # Auto-calculate on the fly if not generated yet
    if not results:
        calculate_subject_internal_results(
            db=db,
            subject_id=subject_id,
            academic_session=academic_session.strip(),
            sections=sections,
        )
        result_query = (
            db.query(InternalResult)
            .filter(
                InternalResult.subject_id == subject_id,
                InternalResult.academic_session == academic_session.strip()
            )
            .options(
                joinedload(InternalResult.student).joinedload(StudentProfile.user),
                joinedload(InternalResult.subject)
            )
        )
        if sections is not None:
            result_query = (
                result_query
                .join(StudentProfile, InternalResult.student_id == StudentProfile.id)
                .filter(StudentProfile.section.in_(sections))
            )
        results = result_query.all()

    return results


# ============================================================================
# 3. Student Personal Internal Marks Award Card
# ============================================================================
@router.get(
    "/my-results",
    response_model=List[InternalResultOut],
    summary="Get Logged-in Student's Internal Results"
)
def get_my_internal_results(
    academic_session: Optional[str] = Query(None, description="Optional academic session filter"),
    db: Session = Depends(get_db),
    student: StudentProfile = Depends(get_current_student_profile)
):
    """
    Allows the logged-in student to view their calculated internal marks (out of 40)
    across all enrolled subjects.
    
    Restricted to: Authenticated Students.
    """
    query = (
        db.query(InternalResult)
        .filter(InternalResult.student_id == student.id)
        .options(
            joinedload(InternalResult.subject),
            joinedload(InternalResult.student).joinedload(StudentProfile.user)
        )
    )

    if academic_session:
        query = query.filter(InternalResult.academic_session == academic_session)

    results = query.all()
    return results


# ============================================================================
# 4. Finalize & Lock Results (HOD or Super Admin only)
# ============================================================================
@router.post(
    "/finalize",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Finalize and Lock Internal Results (HOD / Admin)"
)
def finalize_results(
    payload: FinalizeResultRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hod_or_admin)
):
    """
    Locks the official 40-mark internal results for submission to AWKUM Examination Branch.
    Once finalized (is_finalized = True), marks cannot be modified without HOD approval.
    
    Restricted to: HOD and Super Admin only.
    """
    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {payload.subject_id} not found."
        )
    require_subject_department_access(db, current_user, payload.subject_id)

    records = (
        db.query(InternalResult)
        .filter(
            InternalResult.subject_id == payload.subject_id,
            InternalResult.academic_session == payload.academic_session
        )
        .all()
    )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No internal results found to finalize for subject '{subject.code}' in session '{payload.academic_session}'. Calculate results first."
        )

    # Lock all records
    for rec in records:
        rec.is_finalized = True
        if payload.remarks:
            rec.remarks = payload.remarks

    db.commit()

    for record in records:
        notify_student(
            background_tasks,
            db,
            record.student_id,
            f"Internal result published: {subject.code}",
            "Your internal result has been finalized",
            [
                f"<strong>{html.escape(subject.code)}</strong> · "
                f"{html.escape(payload.academic_session)}: "
                f"{record.total_internal:g} / 40 marks.",
            ],
        )

    return MessageResponse(
        message=f"Successfully finalized and locked internal results for {len(records)} students in '{subject.title}' ({subject.code}) - {payload.academic_session}.",
        success=True,
        details={
            "subject_id": subject.id,
            "subject_code": subject.code,
            "academic_session": payload.academic_session,
            "finalized_count": len(records),
            "approved_by": current_user.full_name
        }
    )
