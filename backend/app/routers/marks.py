"""
Marks Entry Router for Government Post Graduate College Mardan (GPGCM)
Computer Science Department Management System (Phase 1)
Affiliated with Abdul Wali Khan University Mardan (AWKUM)

Handles:
1. Mid-Term Examination Marks Entry (Maximum: 20 Marks)
2. Topic Presentation / Seminar Marks Entry (Maximum: 5 Marks)
"""

import html
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.core.academic import (
    get_faculty_allocation_pairs,
    require_enrolled_students,
    require_faculty_subject_allocation,
)
from app.database import get_db
from app.models.models import (
    User,
    UserRole,
    MidTermMarks,
    PresentationMarks,
    Subject,
    FacultyProfile,
    StudentProfile
)
from app.schemas.schemas import (
    MidTermMarksBulkCreate,
    MidTermMarksOut,
    PresentationMarksBulkCreate,
    PresentationMarksOut
)
from app.core.deps import (
    get_current_user,
    require_faculty_or_admin,
    get_current_student_profile
)
from app.services.notifications import notify_student

router = APIRouter(prefix="/marks", tags=["Mid-Term & Presentation Marks"])


# ============================================================================
# 1. Bulk Mid-Term Marks Entry (Out of 20.0)
# ============================================================================
@router.post(
    "/mid-term/bulk",
    response_model=List[MidTermMarksOut],
    status_code=status.HTTP_200_OK,
    summary="Enter Mid-Term Marks for Multiple Students (Out of 20)"
)
def enter_mid_term_marks_bulk(
    payload: MidTermMarksBulkCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Enters or updates Mid-Term examination marks for multiple students in a subject.
    Maximum marks is strictly 20.0 as per AWKUM / GPGCM criteria.
    
    Validations:
    - Obtained marks must be between 0.0 and 20.0.
    - If a mark already exists for the student and session, it is updated.
    
    Restricted to: Faculty, HOD, and Super Admin.
    """
    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {payload.subject_id} not found."
        )

    # Determine faculty_id
    faculty_id = None
    if current_user.role == UserRole.FACULTY:
        faculty = require_faculty_subject_allocation(
            db, current_user, payload.subject_id, payload.academic_session
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

    require_enrolled_students(
        db,
        current_user,
        payload.subject_id,
        payload.academic_session,
        {item.student_id for item in payload.records},
    )
    saved_records = []
    for item in payload.records:
        if item.obtained_marks < 0.0 or item.obtained_marks > 20.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Obtained marks ({item.obtained_marks}) for student ID {item.student_id} must be between 0.0 and 20.0."
            )

        existing = (
            db.query(MidTermMarks)
            .filter(
                MidTermMarks.subject_id == payload.subject_id,
                MidTermMarks.student_id == item.student_id,
                MidTermMarks.academic_session == payload.academic_session
            )
            .first()
        )

        if existing:
            existing.obtained_marks = item.obtained_marks
            existing.remarks = item.remarks
            existing.faculty_id = faculty_id
            saved_records.append(existing)
        else:
            record = MidTermMarks(
                subject_id=payload.subject_id,
                student_id=item.student_id,
                faculty_id=faculty_id,
                academic_session=payload.academic_session,
                max_marks=20.0,
                obtained_marks=item.obtained_marks,
                remarks=item.remarks
            )
            db.add(record)
            saved_records.append(record)

    db.commit()
    for s in saved_records:
        db.refresh(s)

    for item in payload.records:
        notify_student(
            background_tasks,
            db,
            item.student_id,
            f"Mid-term marks posted: {subject.code}",
            "Your mid-term marks are available",
            [
                f"<strong>{html.escape(subject.code)}</strong> · "
                f"{html.escape(payload.academic_session)}: {item.obtained_marks:g} / 20 marks.",
            ],
        )
    return saved_records


# ============================================================================
# 2. View Mid-Term Marks of a Subject
# ============================================================================
@router.get(
    "/mid-term/subject/{subject_id}",
    response_model=List[MidTermMarksOut],
    summary="Get Mid-Term Marks for a Subject"
)
def get_subject_mid_term_marks(
    subject_id: int,
    academic_session: Optional[str] = Query(None, description="e.g. Fall 2024"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Retrieves all entered Mid-Term marks (out of 20) for the subject.
    Restricted to: Faculty, HOD, and Super Admin.
    """
    query = (
        db.query(MidTermMarks)
        .filter(MidTermMarks.subject_id == subject_id)
        .options(joinedload(MidTermMarks.student).joinedload(StudentProfile.user))
    )
    pairs = get_faculty_allocation_pairs(
        db, current_user, subject_id, academic_session
    )
    if academic_session:
        query = query.filter(MidTermMarks.academic_session == academic_session)
    if pairs is not None:
        query = (
            query.join(StudentProfile, MidTermMarks.student_id == StudentProfile.id)
            .filter(or_(*[
                and_(
                    MidTermMarks.academic_session == session,
                    StudentProfile.section == section,
                )
                for session, section in pairs
            ]))
        )

    return query.order_by(MidTermMarks.id.asc()).all()


# ============================================================================
# 3. Bulk Presentation Marks Entry (Out of 5.0)
# ============================================================================
@router.post(
    "/presentation/bulk",
    response_model=List[PresentationMarksOut],
    status_code=status.HTTP_200_OK,
    summary="Enter Presentation Marks for Multiple Students (Out of 5)"
)
def enter_presentation_marks_bulk(
    payload: PresentationMarksBulkCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Enters or updates Presentation / Seminar marks for multiple students in a subject.
    Maximum marks is strictly 5.0 as per AWKUM / GPGCM criteria.
    
    Validations:
    - Obtained marks must be between 0.0 and 5.0.
    - If a mark already exists for the student and session, it is updated.
    
    Restricted to: Faculty, HOD, and Super Admin.
    """
    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {payload.subject_id} not found."
        )

    # Determine faculty_id
    faculty_id = None
    if current_user.role == UserRole.FACULTY:
        faculty = require_faculty_subject_allocation(
            db, current_user, payload.subject_id, payload.academic_session
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

    require_enrolled_students(
        db,
        current_user,
        payload.subject_id,
        payload.academic_session,
        {item.student_id for item in payload.records},
    )
    saved_records = []
    for item in payload.records:
        if item.obtained_marks < 0.0 or item.obtained_marks > 5.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Presentation marks ({item.obtained_marks}) for student ID {item.student_id} must be between 0.0 and 5.0."
            )

        existing = (
            db.query(PresentationMarks)
            .filter(
                PresentationMarks.subject_id == payload.subject_id,
                PresentationMarks.student_id == item.student_id,
                PresentationMarks.academic_session == payload.academic_session
            )
            .first()
        )

        if existing:
            existing.obtained_marks = item.obtained_marks
            existing.topic = item.topic
            existing.remarks = item.remarks
            existing.faculty_id = faculty_id
            saved_records.append(existing)
        else:
            record = PresentationMarks(
                subject_id=payload.subject_id,
                student_id=item.student_id,
                faculty_id=faculty_id,
                academic_session=payload.academic_session,
                topic=item.topic,
                max_marks=5.0,
                obtained_marks=item.obtained_marks,
                remarks=item.remarks
            )
            db.add(record)
            saved_records.append(record)

    db.commit()
    for s in saved_records:
        db.refresh(s)

    for item in payload.records:
        notify_student(
            background_tasks,
            db,
            item.student_id,
            f"Presentation marks posted: {subject.code}",
            "Your presentation marks are available",
            [
                f"<strong>{html.escape(subject.code)}</strong> · "
                f"{html.escape(payload.academic_session)}: {item.obtained_marks:g} / 5 marks.",
            ],
        )
    return saved_records


# ============================================================================
# 4. View Presentation Marks of a Subject
# ============================================================================
@router.get(
    "/presentation/subject/{subject_id}",
    response_model=List[PresentationMarksOut],
    summary="Get Presentation Marks for a Subject"
)
def get_subject_presentation_marks(
    subject_id: int,
    academic_session: Optional[str] = Query(None, description="e.g. Fall 2024"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Retrieves all entered Presentation marks (out of 5) for the subject.
    Restricted to: Faculty, HOD, and Super Admin.
    """
    query = (
        db.query(PresentationMarks)
        .filter(PresentationMarks.subject_id == subject_id)
        .options(joinedload(PresentationMarks.student).joinedload(StudentProfile.user))
    )
    pairs = get_faculty_allocation_pairs(
        db, current_user, subject_id, academic_session
    )
    if academic_session:
        query = query.filter(PresentationMarks.academic_session == academic_session)
    if pairs is not None:
        query = (
            query.join(StudentProfile, PresentationMarks.student_id == StudentProfile.id)
            .filter(or_(*[
                and_(
                    PresentationMarks.academic_session == session,
                    StudentProfile.section == section,
                )
                for session, section in pairs
            ]))
        )

    return query.order_by(PresentationMarks.id.asc()).all()


# ============================================================================
# 5. Student Views Own Mid-Term & Presentation Marks
# ============================================================================
@router.get(
    "/my-marks",
    summary="Student Personal Mid-Term and Presentation Marks"
)
def get_my_marks(
    academic_session: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    student: StudentProfile = Depends(get_current_student_profile)
):
    """
    Returns the currently logged-in student's Mid-Term (out of 20)
    and Presentation (out of 5) marks across enrolled subjects.
    
    Restricted to: Authenticated Students.
    """
    mid_query = db.query(MidTermMarks).filter(MidTermMarks.student_id == student.id)
    pres_query = db.query(PresentationMarks).filter(PresentationMarks.student_id == student.id)

    if academic_session:
        mid_query = mid_query.filter(MidTermMarks.academic_session == academic_session)
        pres_query = pres_query.filter(PresentationMarks.academic_session == academic_session)

    mid_records = mid_query.all()
    pres_records = pres_query.all()

    # Organize by subject
    subjects_dict = {}
    for m in mid_records:
        subj = db.query(Subject).filter(Subject.id == m.subject_id).first()
        subj_code = subj.code if subj else f"Subject-{m.subject_id}"
        subj_title = subj.title if subj else "Unknown"
        subjects_dict[m.subject_id] = {
            "subject_id": m.subject_id,
            "subject_code": subj_code,
            "subject_title": subj_title,
            "academic_session": m.academic_session,
            "mid_term": {
                "obtained": m.obtained_marks,
                "max": m.max_marks,
                "remarks": m.remarks
            },
            "presentation": None
        }

    for p in pres_records:
        if p.subject_id in subjects_dict:
            subjects_dict[p.subject_id]["presentation"] = {
                "topic": p.topic,
                "obtained": p.obtained_marks,
                "max": p.max_marks,
                "remarks": p.remarks
            }
        else:
            subj = db.query(Subject).filter(Subject.id == p.subject_id).first()
            subj_code = subj.code if subj else f"Subject-{p.subject_id}"
            subj_title = subj.title if subj else "Unknown"
            subjects_dict[p.subject_id] = {
                "subject_id": p.subject_id,
                "subject_code": subj_code,
                "subject_title": subj_title,
                "academic_session": p.academic_session,
                "mid_term": None,
                "presentation": {
                    "topic": p.topic,
                    "obtained": p.obtained_marks,
                    "max": p.max_marks,
                    "remarks": p.remarks
                }
            }

    return {
        "student_id": student.id,
        "roll_number": student.roll_number,
        "subjects": list(subjects_dict.values())
    }
