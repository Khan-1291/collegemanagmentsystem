"""
Subjects & Allocations Router for Government Post Graduate College Mardan (GPGCM)
Computer Science Department Management System (Phase 1)
Affiliated with Abdul Wali Khan University Mardan (AWKUM)

Handles:
- Subject creation (HOD / Admin)
- Listing curriculum subjects (filtered by semester)
- Faculty subject allocations (teacher assigned to course for a session & section)
- Student subject enrollments (bulk enrollment of cohort)
- User personalized subject listing (/my-subjects for Faculty and Students)
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.models import (
    User,
    UserRole,
    Subject,
    FacultySubject,
    StudentSubject,
    StudentProfile,
    FacultyProfile,
    Department,
    EnrollmentStatus
)
from app.schemas.schemas import (
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
    FacultySubjectCreate,
    FacultySubjectOut,
    StudentBulkEnrollRequest,
    StudentSubjectOut,
    MessageResponse
)
from app.core.deps import (
    get_current_user,
    get_user_department_id,
    require_department_access,
    require_hod_only,
    require_hod_or_admin,
    require_faculty_or_admin
)
from app.services.bulk_import import ensure_computer_science_department

router = APIRouter(prefix="/subjects", tags=["Subjects & Allocations"])


# ============================================================================
# 1. Create a Subject (HOD / Admin)
# ============================================================================
@router.post(
    "/",
    response_model=SubjectOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Curriculum Subject (HOD / Admin)"
)
def create_subject(
    payload: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hod_or_admin)
):
    """
    Creates a new BS Computer Science subject course.
    Restricted to: HOD and Super Admin.
    """
    clean_code = payload.code.strip().upper()
    clean_title = payload.title.strip()
    if not clean_code or not clean_title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Subject code and title must not be empty."
        )
    if db.query(Subject).filter(Subject.code == clean_code).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject with code '{clean_code}' already exists."
        )

    if current_user.role == UserRole.SUPER_ADMIN and payload.department_id is None:
        department = ensure_computer_science_department(db)
        dept_id = department.id
    else:
        dept_id = get_user_department_id(db, current_user) if current_user.role != UserRole.SUPER_ADMIN else payload.department_id
        if current_user.role != UserRole.SUPER_ADMIN and payload.department_id is not None and payload.department_id != dept_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can create subjects only in your assigned department.",
            )
        department = db.query(Department).filter(Department.id == dept_id).first()
        if department is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {dept_id} not found."
            )

    subject = Subject(
        department_id=dept_id,
        code=clean_code,
        title=clean_title,
        credit_hours=payload.credit_hours,
        semester=payload.semester,
        description=payload.description,
        is_active=payload.is_active
    )
    db.add(subject)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Subject code '{clean_code}' is already in use."
        ) from exc
    db.refresh(subject)
    return subject


# ============================================================================
# 3. Update a Subject (HOD / Admin)
# ============================================================================
@router.put(
    "/{subject_id}",
    response_model=SubjectOut,
    summary="Update or Deactivate Curriculum Subject (HOD / Admin)"
)
def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hod_or_admin)
):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} not found."
        )
    require_department_access(db, current_user, subject.department_id)

    updates = payload.model_dump(exclude_unset=True)
    if "code" in updates:
        updates["code"] = updates["code"].strip().upper()
        if not updates["code"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Subject code must not be empty."
            )
        duplicate = db.query(Subject).filter(
            Subject.code == updates["code"],
            Subject.id != subject_id
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Subject code '{updates['code']}' is already in use."
            )
    if "title" in updates:
        updates["title"] = updates["title"].strip()
        if not updates["title"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Subject title must not be empty."
            )

    for field, value in updates.items():
        setattr(subject, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The subject could not be saved because its code is already in use."
        ) from exc
    db.refresh(subject)
    return subject


# ============================================================================
# 2. List All Curriculum Subjects
# ============================================================================
@router.get(
    "/",
    response_model=List[SubjectOut],
    summary="List All Curriculum Subjects"
)
def list_subjects(
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester (1-8)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    department_id: Optional[int] = Query(None, description="Super Admin department filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists curriculum subjects for the Computer Science department.
    Accessible to all authenticated users.
    """
    query = db.query(Subject)
    if current_user.role == UserRole.SUPER_ADMIN:
        if department_id is not None:
            query = query.filter(Subject.department_id == department_id)
    else:
        query = query.filter(Subject.department_id == get_user_department_id(db, current_user))
    if semester is not None:
        query = query.filter(Subject.semester == semester)
    if is_active is not None:
        query = query.filter(Subject.is_active == is_active)

    return query.order_by(Subject.semester.asc(), Subject.code.asc()).all()


# ============================================================================
# 4. Allocate Subject to Faculty Member (HOD / Admin)
# ============================================================================
@router.post(
    "/allocate-faculty",
    response_model=FacultySubjectOut,
    status_code=status.HTTP_200_OK,
    summary="Allocate Subject to Faculty Member (HOD / Admin)"
)
def allocate_subject_to_faculty(
    payload: FacultySubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hod_or_admin)
):
    """
    Assigns a faculty teacher to a subject for a specific semester/session and section.
    Restricted to: HOD and Super Admin.
    """
    faculty = (
        db.query(FacultyProfile)
        .join(User, FacultyProfile.user_id == User.id)
        .filter(FacultyProfile.id == payload.faculty_id, User.is_active.is_(True))
        .first()
    )
    if not faculty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Faculty with ID {payload.faculty_id} not found."
        )

    subject = db.query(Subject).filter(
        Subject.id == payload.subject_id,
        Subject.is_active.is_(True)
    ).first()
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active subject with ID {payload.subject_id} not found."
        )
    require_department_access(db, current_user, subject.department_id)
    academic_session = payload.academic_session.strip()
    section = payload.section.strip().upper()
    if not academic_session or not section:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Academic session and section must not be empty."
        )
    existing = (
        db.query(FacultySubject)
        .filter(
            FacultySubject.faculty_id == payload.faculty_id,
            FacultySubject.subject_id == payload.subject_id,
            FacultySubject.academic_session == academic_session,
            FacultySubject.section == section
        )
        .first()
    )

    if existing:
        return existing

    allocation = FacultySubject(
        faculty_id=payload.faculty_id,
        subject_id=payload.subject_id,
        academic_session=academic_session,
        section=section
    )
    db.add(allocation)
    db.commit()
    db.refresh(allocation)
    return allocation


# ============================================================================
# 5. List Faculty Allocations (HOD / Admin)
# ============================================================================
@router.get(
    "/allocations",
    response_model=List[FacultySubjectOut],
    summary="List Faculty Subject Allocations (HOD / Admin)"
)
def list_faculty_allocations(
    academic_session: Optional[str] = Query(None, description="Filter by academic session"),
    department_id: Optional[int] = Query(None, description="Super Admin department filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hod_or_admin)
):
    query = (
        db.query(FacultySubject)
        .join(Subject, FacultySubject.subject_id == Subject.id)
        .options(
            joinedload(FacultySubject.subject),
            joinedload(FacultySubject.faculty).joinedload(FacultyProfile.user)
        )
    )
    if current_user.role == UserRole.SUPER_ADMIN:
        if department_id is not None:
            query = query.filter(Subject.department_id == department_id)
    else:
        query = query.filter(Subject.department_id == get_user_department_id(db, current_user))
    if academic_session:
        query = query.filter(FacultySubject.academic_session == academic_session.strip())
    return query.order_by(
        FacultySubject.academic_session.desc(),
        FacultySubject.section.asc(),
        FacultySubject.subject_id.asc()
    ).all()


@router.delete(
    "/allocations/{allocation_id}",
    response_model=MessageResponse,
    summary="Remove a Faculty Subject Allocation (HOD / Admin)"
)
def remove_faculty_allocation(
    allocation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hod_or_admin)
):
    allocation = db.query(FacultySubject).filter(
        FacultySubject.id == allocation_id
    ).first()
    if allocation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allocation with ID {allocation_id} not found."
        )
    require_department_access(db, current_user, allocation.subject.department_id)
    db.delete(allocation)
    db.commit()
    return MessageResponse(message="Faculty allocation removed.")


# ============================================================================
# 6. Bulk Enroll Multiple Students in a Subject (HOD)
# ============================================================================
@router.post(
    "/enroll-students",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Enroll Multiple Students into a Subject (HOD)"
)
def enroll_multiple_students(
    payload: StudentBulkEnrollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hod_only)
):
    """
    Enrolls multiple students into a subject for an academic session.
    Restricted to: HOD within their assigned department.
    """
    subject = db.query(Subject).filter(
        Subject.id == payload.subject_id,
        Subject.is_active.is_(True)
    ).first()
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active subject with ID {payload.subject_id} not found."
        )
    require_department_access(db, current_user, subject.department_id)

    students = (
        db.query(StudentProfile)
        .filter(StudentProfile.id.in_(set(payload.student_ids)))
        .all()
    )
    found_student_ids = {student.id for student in students}
    missing_student_ids = sorted(set(payload.student_ids) - found_student_ids)
    if missing_student_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student profile(s) not found: {', '.join(map(str, missing_student_ids))}."
        )

    mismatched_departments = [
        student.id for student in students
        if student.department_id != subject.department_id
    ]
    if mismatched_departments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Student profile(s) {', '.join(map(str, mismatched_departments))} "
                "belong to a different department from this subject."
            ),
        )
    mismatched_students = [
        student.id for student in students if student.semester != subject.semester
    ]
    if mismatched_students:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Student profile(s) {', '.join(map(str, mismatched_students))} are not in semester {subject.semester}."
        )

    enrolled_count = 0
    academic_session = payload.academic_session.strip()
    if not academic_session:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Academic session must not be empty."
        )
    for sid in set(payload.student_ids):
        existing = (
            db.query(StudentSubject)
            .filter(
                StudentSubject.student_id == sid,
                StudentSubject.subject_id == payload.subject_id,
                StudentSubject.academic_session == academic_session
            )
            .first()
        )

        if not existing:
            new_enrollment = StudentSubject(
                student_id=sid,
                subject_id=payload.subject_id,
                academic_session=academic_session,
                status=EnrollmentStatus.ENROLLED
            )
            db.add(new_enrollment)
            enrolled_count += 1

    db.commit()

    return MessageResponse(
        message=f"Successfully enrolled {enrolled_count} students into '{subject.title}' ({subject.code}) for {payload.academic_session}.",
        success=True,
        details={
            "subject_id": subject.id,
            "subject_code": subject.code,
            "academic_session": academic_session,
            "enrolled_count": enrolled_count
        }
    )


# ============================================================================
# 7. User Personalized Subjects View (/my-subjects)
# ============================================================================
@router.get(
    "/my-subjects",
    summary="Get Current User's Enrolled or Taught Subjects"
)
def get_my_subjects(
    academic_session: Optional[str] = Query(None, description="e.g. Fall 2024"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns subjects relevant to the logged-in user:
    - If Faculty / HOD: returns subjects assigned to teach.
    - If Student: returns subjects enrolled to study.
    - If Super Admin: returns all active subjects.
    """
    # 1. Faculty / HOD
    if current_user.role in [UserRole.FACULTY, UserRole.HOD]:
        fac = db.query(FacultyProfile).filter(FacultyProfile.user_id == current_user.id).first()
        if not fac:
            return []

        query = (
            db.query(FacultySubject)
            .filter(FacultySubject.faculty_id == fac.id)
            .options(joinedload(FacultySubject.subject))
        )
        if academic_session:
            query = query.filter(FacultySubject.academic_session == academic_session)

        allocations = query.all()
        return [
            {
                "subject_id": a.subject.id,
                "code": a.subject.code,
                "title": a.subject.title,
                "credit_hours": a.subject.credit_hours,
                "semester": a.subject.semester,
                "academic_session": a.academic_session,
                "section": a.section,
                "role": "instructor"
            }
            for a in allocations
        ]

    # 2. Student
    elif current_user.role == UserRole.STUDENT:
        student = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
        if not student:
            return []

        query = (
            db.query(StudentSubject)
            .filter(
                StudentSubject.student_id == student.id,
                StudentSubject.status == EnrollmentStatus.ENROLLED,
                Subject.is_active.is_(True),
            )
            .join(Subject, StudentSubject.subject_id == Subject.id)
            .options(joinedload(StudentSubject.subject))
        )
        if academic_session:
            query = query.filter(StudentSubject.academic_session == academic_session)

        enrollments = query.all()
        return [
            {
                "subject_id": e.subject.id,
                "code": e.subject.code,
                "title": e.subject.title,
                "credit_hours": e.subject.credit_hours,
                "semester": e.subject.semester,
                "academic_session": e.academic_session,
                "status": e.status.value,
                "role": "student"
            }
            for e in enrollments
        ]

    # 3. Super Admin
    else:
        subjects = db.query(Subject).filter(Subject.is_active == True).all()
        return [
            {
                "subject_id": s.id,
                "code": s.code,
                "title": s.title,
                "credit_hours": s.credit_hours,
                "semester": s.semester,
                "role": "administrator"
            }
            for s in subjects
        ]
