"""
Attendance Router for Government Post Graduate College Mardan (GPGCM)
Computer Science Department Management System (Phase 1)
Affiliated with Abdul Wali Khan University Mardan (AWKUM)

Handles Daily Attendance Marking (Present / Absent / Leave)
and Auto-Calculation of Attendance Percentages and Slabs:
- >= 90%   -> 5 Marks
- 80 - 89% -> 4 Marks
- 75 - 79% -> 3 Marks
- 70 - 74% -> 2 Marks
- 65 - 69% -> 1 Mark
- < 65%    -> 0 Marks
"""

from datetime import date
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from sqlalchemy import and_, or_

from app.core.academic import (
    get_faculty_allocation_pairs,
    require_faculty_subject_allocation,
)
from app.database import get_db
from app.models.models import (
    User,
    UserRole,
    Attendance,
    AttendanceStatus,
    Subject,
    StudentProfile,
    StudentSubject,
    FacultyProfile,
    EnrollmentStatus,
)
from app.schemas.schemas import (
    AttendanceBulkCreate,
    AttendanceOut,
    AttendanceStudentSummary,
    MessageResponse
)
from app.services.marks_calculator import calculate_attendance_marks
from app.core.deps import (
    get_current_user,
    require_faculty_or_admin,
    get_current_student_profile
)

router = APIRouter(prefix="/attendance", tags=["Attendance Management"])


# ============================================================================
# 1. Mark Bulk Attendance for a Subject on a Date (Faculty / Admin)
# ============================================================================
@router.post(
    "/bulk",
    response_model=List[AttendanceOut],
    status_code=status.HTTP_200_OK,
    summary="Mark Attendance for Multiple Students on a Date"
)
def mark_attendance_bulk(
    payload: AttendanceBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Allows faculty to record daily class attendance (Present, Absent, Leave)
    for multiple students in a single request.
    
    If attendance was already recorded for a student on the specified date,
    it updates the existing record (safe for corrections).
    
    Restricted to: Faculty, HOD, and Super Admin.
    """
    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {payload.subject_id} not found."
        )

    faculty = require_faculty_subject_allocation(
        db,
        current_user,
        payload.subject_id,
        payload.academic_session,
        payload.section,
    )
    if faculty is None:
        faculty = db.query(FacultyProfile).filter(
            FacultyProfile.user_id == current_user.id
        ).first() or db.query(FacultyProfile).first()
    if faculty is None:
        raise HTTPException(status_code=400, detail="Faculty profile not found.")
    faculty_id = faculty.id

    requested_student_ids = {item.student_id for item in payload.records}
    eligible_students = (
        db.query(StudentProfile.id)
        .join(User, StudentProfile.user_id == User.id)
        .join(StudentSubject, StudentSubject.student_id == StudentProfile.id)
        .filter(
            StudentSubject.subject_id == payload.subject_id,
            StudentSubject.academic_session == payload.academic_session.strip(),
            StudentSubject.status == EnrollmentStatus.ENROLLED,
            StudentProfile.section == payload.section.strip().upper(),
            User.is_active.is_(True),
            StudentProfile.id.in_(requested_student_ids),
        )
        .all()
    )
    eligible_ids = {student_id for (student_id,) in eligible_students}
    invalid_ids = sorted(requested_student_ids - eligible_ids)
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Student profile(s) {', '.join(map(str, invalid_ids))} are not active and enrolled in this subject, session, and section."
        )

    saved_records = []
    for item in payload.records:
        existing_record = (
            db.query(Attendance)
            .filter(
                Attendance.subject_id == payload.subject_id,
                Attendance.student_id == item.student_id,
                Attendance.academic_session == payload.academic_session.strip(),
                Attendance.date == payload.date
            )
            .first()
        )

        if existing_record:
            # Update existing
            existing_record.status = item.status
            existing_record.remarks = item.remarks
            existing_record.faculty_id = faculty_id
            saved_records.append(existing_record)
        else:
            # Create new
            new_record = Attendance(
                subject_id=payload.subject_id,
                faculty_id=faculty_id,
                student_id=item.student_id,
                academic_session=payload.academic_session.strip(),
                date=payload.date,
                status=item.status,
                remarks=item.remarks
            )
            db.add(new_record)
            saved_records.append(new_record)

    db.commit()
    for rec in saved_records:
        db.refresh(rec)

    return saved_records


@router.get(
    "/subject/{subject_id}/roster",
    summary="Get Enrolled Students and Attendance Summary for a Class"
)
def get_attendance_roster(
    subject_id: int,
    academic_session: str = Query(..., min_length=1, max_length=30),
    section: str = Query("A", min_length=1, max_length=10),
    attendance_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if subject is None:
        raise HTTPException(status_code=404, detail=f"Subject with ID {subject_id} not found.")

    require_faculty_subject_allocation(
        db, current_user, subject_id, academic_session, section
    )
    students = (
        db.query(StudentProfile)
        .join(User, StudentProfile.user_id == User.id)
        .join(StudentSubject, StudentSubject.student_id == StudentProfile.id)
        .filter(
            StudentSubject.subject_id == subject_id,
            StudentSubject.academic_session == academic_session.strip(),
            StudentSubject.status == EnrollmentStatus.ENROLLED,
            StudentProfile.section == section.strip().upper(),
            User.is_active.is_(True),
        )
        .options(joinedload(StudentProfile.user))
        .order_by(StudentProfile.roll_number.asc())
        .all()
    )

    roster = []
    for student in students:
        records = db.query(Attendance).filter(
            Attendance.subject_id == subject_id,
            Attendance.student_id == student.id,
            Attendance.academic_session == academic_session.strip(),
        ).all()
        total = len(records)
        present = sum(record.status == AttendanceStatus.PRESENT for record in records)
        daily_record = next(
            (
                record for record in records
                if attendance_date is not None and record.date == attendance_date
            ),
            None,
        )
        roster.append({
            "student_id": student.id,
            "roll_number": student.roll_number,
            "full_name": student.user.full_name,
            "attendance_status": daily_record.status.value if daily_record else None,
            "total_lectures": total,
            "present_count": present,
            "attendance_percentage": round(present * 100.0 / total, 2) if total else 0.0,
        })
    return roster


# ============================================================================
# 2. View Attendance of a Subject (Filtered by Date or Date Range)
# ============================================================================
@router.get(
    "/subject/{subject_id}",
    response_model=List[AttendanceOut],
    summary="View Attendance Records of a Subject"
)
def get_subject_attendance(
    subject_id: int,
    academic_session: Optional[str] = Query(None, description="Filter by academic session"),
    attendance_date: Optional[date] = Query(None, description="Filter by exact date (YYYY-MM-DD)"),
    student_id: Optional[int] = Query(None, description="Filter by student ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Retrieves attendance records for a specific subject.
    Can be filtered by date or student ID.
    
    Restricted to: Faculty, HOD, and Super Admin.
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} not found."
        )

    pairs = get_faculty_allocation_pairs(
        db, current_user, subject_id, academic_session
    )
    query = db.query(Attendance).filter(Attendance.subject_id == subject_id)

    if academic_session:
        query = query.filter(Attendance.academic_session == academic_session.strip())
    if pairs is not None:
        query = (
            query.join(StudentProfile, Attendance.student_id == StudentProfile.id)
            .filter(or_(*[
                and_(
                    Attendance.academic_session == session,
                    StudentProfile.section == section,
                )
                for session, section in pairs
            ]))
        )
    if attendance_date:
        query = query.filter(Attendance.date == attendance_date)
    if student_id:
        query = query.filter(Attendance.student_id == student_id)

    records = query.order_by(Attendance.date.desc(), Attendance.id.asc()).all()
    return records


# ============================================================================
# 3. Student Views Personal Attendance + Percentage Across Enrolled Subjects
# ============================================================================
@router.get(
    "/my-attendance",
    summary="Student Personal Attendance Breakdown & Percentage"
)
def get_my_attendance(
    db: Session = Depends(get_db),
    student: StudentProfile = Depends(get_current_student_profile)
):
    """
    Returns complete attendance stats for the currently logged-in student
    across all subjects they are enrolled in.
    
    Includes:
    - Subject details (code, title)
    - Total classes conducted
    - Count of Present, Absent, Leave
    - Attendance percentage
    - Exact calculated marks (out of 5)
    - Recent attendance log history
    
    Restricted to: Authenticated Students.
    """
    enrollments = (
        db.query(StudentSubject)
        .filter(
            StudentSubject.student_id == student.id,
            StudentSubject.status == EnrollmentStatus.ENROLLED,
        )
        .options(joinedload(StudentSubject.subject))
        .all()
    )

    attendance_overview = []

    for enr in enrollments:
        records = (
            db.query(Attendance)
            .filter(
                Attendance.subject_id == enr.subject_id,
                Attendance.student_id == student.id,
                Attendance.academic_session == enr.academic_session,
            )
            .order_by(Attendance.date.desc())
            .all()
        )

        total_lectures = len(records)
        present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        leave_count = sum(1 for r in records if r.status == AttendanceStatus.LEAVE)

        percentage = (
            round((present_count / total_lectures) * 100.0, 2)
            if total_lectures > 0
            else 0.0
        )
        calculated_marks = calculate_attendance_marks(percentage)

        attendance_overview.append({
            "subject_id": enr.subject.id,
            "subject_code": enr.subject.code,
            "subject_title": enr.subject.title,
            "academic_session": enr.academic_session,
            "total_lectures": total_lectures,
            "present_count": present_count,
            "absent_count": absent_count,
            "leave_count": leave_count,
            "attendance_percentage": percentage,
            "calculated_marks": calculated_marks,
            "is_eligible_for_exam": percentage >= 65.0,  # AWKUM 65% minimum rule
            "recent_records": [
                {
                    "date": r.date.isoformat(),
                    "status": r.status.value,
                    "remarks": r.remarks
                }
                for r in records[:15]  # Last 15 sessions
            ]
        })

    return {
        "student_id": student.id,
        "roll_number": student.roll_number,
        "reg_number": student.reg_number,
        "semester": student.semester,
        "total_enrolled_subjects": len(enrollments),
        "subjects": attendance_overview
    }
