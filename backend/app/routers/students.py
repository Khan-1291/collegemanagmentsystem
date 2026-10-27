"""
Students Management Router for Government Post Graduate College Mardan (GPGCM)
Computer Science Department Management System (Phase 1)
Affiliated with Abdul Wali Khan University Mardan (AWKUM)

Handles:
- HOD registering student user account & StudentProfile in their department
- Listing student profiles with filtering (semester, session, section, search)
- Retrieving individual student profile by ID
- Updating student academic and profile data
"""

from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.models import (
    User,
    UserRole,
    StudentProfile
)
from app.schemas.schemas import (
    StudentProfileOut,
    StudentRegisterRequest,
    StudentProfileUpdate
)
from app.core.security import get_password_hash
from app.core.deps import (
    get_current_user,
    get_user_department_id,
    require_hod_only,
    require_faculty_or_admin,
    require_department_access,
)
from app.services.bulk_import import duplicate_rows, parse_import_file, resolve_enrollment_department
from app.services.email_service import queue_welcome_email

router = APIRouter(prefix="/students", tags=["Students Management"])


# ============================================================================
# 1. Register Student User Account + Profile (HOD)
# ============================================================================
@router.post(
    "/bulk-import",
    status_code=status.HTTP_201_CREATED,
    summary="Create Student Accounts from CSV (HOD)",
)
async def bulk_import_students(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="UTF-8 CSV using the student enrollment headers"),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hod_only),
):
    """Create student user accounts and profiles atomically from a CSV file."""
    records = await parse_import_file(
        file,
        StudentRegisterRequest,
        {
            "email",
            "password",
            "full_name",
            "roll_number",
            "reg_number",
            "session",
            "semester",
        },
    )
    duplicate_emails = duplicate_rows(records, "email")
    duplicate_rolls = duplicate_rows(records, "roll_number")
    duplicate_regs = duplicate_rows(records, "reg_number")
    conflicts = []

    for row_number, record in records:
        email = record.email.lower()
        roll_number = record.roll_number.strip().upper()
        reg_number = record.reg_number.strip().upper()
        if (
            row_number in duplicate_emails
            or db.query(User).filter(User.email == email).first()
        ):
            conflicts.append({"row": row_number, "field": "email", "message": "Already registered or repeated in this file."})
        if (
            row_number in duplicate_rolls
            or db.query(StudentProfile).filter(StudentProfile.roll_number == roll_number).first()
        ):
            conflicts.append({"row": row_number, "field": "roll_number", "message": "Already registered or repeated in this file."})
        if (
            row_number in duplicate_regs
            or db.query(StudentProfile).filter(StudentProfile.reg_number == reg_number).first()
        ):
            conflicts.append({"row": row_number, "field": "reg_number", "message": "Already registered or repeated in this file."})

    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Import was not applied because records conflict.", "rows": conflicts},
        )

    try:
        department = resolve_enrollment_department(db, current_user, department_id)
        created = []
        for row_number, payload in records:
            user = User(
                email=payload.email.lower().strip(),
                hashed_password=get_password_hash(payload.password),
                full_name=payload.full_name.strip(),
                role=UserRole.STUDENT,
                phone=payload.phone,
                is_active=True,
            )
            db.add(user)
            db.flush()

            profile = StudentProfile(
                user_id=user.id,
                department_id=department.id,
                roll_number=payload.roll_number.strip().upper(),
                reg_number=payload.reg_number.strip().upper(),
                session=payload.session.strip(),
                semester=payload.semester,
                section=payload.section.strip().upper(),
                program="BS Computer Science",
                guardian_name=payload.guardian_name,
                guardian_phone=payload.guardian_phone,
            )
            db.add(profile)
            db.flush()
            created.append({"row": row_number, "email": user.email, "profile_id": profile.id})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Import was not applied because a record conflicts with existing data.",
        ) from exc

    for _, payload in records:
        queue_welcome_email(
            background_tasks,
            payload.email.lower().strip(),
            payload.full_name.strip(),
            payload.password,
        )
    return {"created": len(created), "records": created}


@router.post(
    "/register",
    response_model=StudentProfileOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register Student Account & Profile (HOD)"
)
def register_student(
    payload: StudentRegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hod_only)
):
    """
    Registers a new student by creating both the User login account
    and the linked StudentProfile record with AWKUM registration and college roll numbers.
    
    Restricted to: HOD within their assigned department.
    """
    clean_email = payload.email.lower().strip()
    clean_roll = payload.roll_number.strip().upper()
    clean_reg = payload.reg_number.strip().upper()

    # Validate uniqueness
    if db.query(User).filter(User.email == clean_email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{clean_email}' is already registered."
        )

    if db.query(StudentProfile).filter(StudentProfile.roll_number == clean_roll).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"College roll number '{clean_roll}' already exists."
        )

    if db.query(StudentProfile).filter(StudentProfile.reg_number == clean_reg).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"AWKUM registration number '{clean_reg}' already exists."
        )

    department = resolve_enrollment_department(db, current_user, payload.department_id)

    # Create User account
    user = User(
        email=clean_email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name.strip(),
        role=UserRole.STUDENT,
        phone=payload.phone,
        is_active=True
    )
    db.add(user)
    db.flush()

    # Create StudentProfile
    profile = StudentProfile(
        user_id=user.id,
        department_id=department.id,
        roll_number=clean_roll,
        reg_number=clean_reg,
        session=payload.session.strip(),
        semester=payload.semester,
        section=payload.section.strip().upper(),
        program="BS Computer Science",
        guardian_name=payload.guardian_name,
        guardian_phone=payload.guardian_phone
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    queue_welcome_email(
        background_tasks,
        user.email,
        user.full_name,
        payload.password,
    )
    return profile


# ============================================================================
# 2. List Students (Filter by Semester, Session, Section, Search)
# ============================================================================
@router.get(
    "/",
    response_model=List[StudentProfileOut],
    summary="List Students with Filtering (Faculty / Admin)"
)
def list_students(
    semester: Optional[int] = Query(None, ge=1, le=8, description="Filter by semester 1-8"),
    session: Optional[str] = Query(None, description="e.g. 2022-2026"),
    section: Optional[str] = Query(None, description="e.g. A or B"),
    search: Optional[str] = Query(None, description="Search by Name, Roll No or Reg No"),
    department_id: Optional[int] = Query(None, description="Super Admin department filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_faculty_or_admin)
):
    """
    Lists students in the Computer Science department.
    Allows filtering by semester, academic session, section, or keyword search.
    
    Restricted to: Faculty, HOD, and Super Admin.
    """
    query = (
        db.query(StudentProfile)
        .join(User, StudentProfile.user_id == User.id)
        .options(joinedload(StudentProfile.user))
    )
    if current_user.role == UserRole.SUPER_ADMIN:
        if department_id is not None:
            query = query.filter(StudentProfile.department_id == department_id)
    else:
        query = query.filter(
            StudentProfile.department_id == get_user_department_id(db, current_user)
        )

    if semester is not None:
        query = query.filter(StudentProfile.semester == semester)
    if session:
        query = query.filter(StudentProfile.session == session.strip())
    if section:
        query = query.filter(StudentProfile.section == section.strip().upper())
    if search:
        search_kw = f"%{search.strip()}%"
        query = query.filter(
            (StudentProfile.roll_number.ilike(search_kw)) |
            (StudentProfile.reg_number.ilike(search_kw)) |
            (User.full_name.ilike(search_kw))
        )

    return query.order_by(StudentProfile.roll_number.asc()).all()


# ============================================================================
# 3. Get Student Profile by ID
# ============================================================================
@router.get(
    "/{student_id}",
    response_model=StudentProfileOut,
    summary="Get Student Profile by ID"
)
def get_student_by_id(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves student profile by student ID.
    Students can only view their own profile.
    Faculty, HOD, and Super Admin can view any student.
    """
    student = (
        db.query(StudentProfile)
        .filter(StudentProfile.id == student_id)
        .options(joinedload(StudentProfile.user))
        .first()
    )
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found."
        )

    if current_user.role != UserRole.STUDENT:
        require_department_access(db, current_user, student.department_id)

    # Privacy check for students
    if current_user.role == UserRole.STUDENT and student.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view other students' profiles."
        )

    return student


# ============================================================================
# 4. Update Student Profile (HOD)
# ============================================================================
@router.put(
    "/{student_id}",
    response_model=StudentProfileOut,
    summary="Update Student Profile (HOD)"
)
def update_student(
    student_id: int,
    payload: StudentProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hod_only)
):
    """
    Updates student academic standing (semester, session, section, guardian details).
    Restricted to: HOD within their assigned department.
    """
    student = db.query(StudentProfile).filter(StudentProfile.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found."
        )
    require_department_access(db, current_user, student.department_id)

    if payload.session is not None:
        student.session = payload.session.strip()
    if payload.semester is not None:
        student.semester = payload.semester
    if payload.section is not None:
        student.section = payload.section.strip().upper()
    if payload.guardian_name is not None:
        student.guardian_name = payload.guardian_name.strip()
    if payload.guardian_phone is not None:
        student.guardian_phone = payload.guardian_phone.strip()

    db.commit()
    db.refresh(student)
    return student
