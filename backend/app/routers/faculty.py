"""
Faculty Management Router for Government Post Graduate College Mardan (GPGCM)
Computer Science Department Management System (Phase 1)
Affiliated with Abdul Wali Khan University Mardan (AWKUM)

Handles:
- Super Admin registering faculty user account & FacultyProfile
- Listing the global faculty directory to Super Admin and HOD
- Viewing detailed faculty profile by ID
- Logged-in faculty viewing their own profile (/my-profile)
"""

from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.models import (
    User,
    UserRole,
    FacultyProfile
)
from app.schemas.schemas import (
    FacultyProfileOut,
    FacultyRegisterRequest,
    FacultyProfileUpdate
)
from app.core.security import get_password_hash
from app.core.deps import (
    get_current_user,
    get_user_department_id,
    require_super_admin,
    get_current_faculty_profile,
    require_department_access,
)
from app.services.bulk_import import (
    duplicate_rows,
    resolve_enrollment_department,
    parse_import_file,
)
from app.services.email_service import queue_welcome_email

router = APIRouter(prefix="/faculty", tags=["Faculty Management"])


# ============================================================================
# 1. Register Faculty Member (Super Admin)
# ============================================================================
@router.post(
    "/bulk-import",
    status_code=status.HTTP_201_CREATED,
    summary="Create Faculty Accounts from CSV (Super Admin)",
)
async def bulk_import_faculty(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="UTF-8 CSV using the faculty enrollment headers"),
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Create faculty user accounts and profiles atomically from a CSV file."""
    records = await parse_import_file(
        file,
        FacultyRegisterRequest,
        {"email", "password", "full_name", "designation", "qualification"},
    )
    duplicate_emails = duplicate_rows(records, "email")
    conflicts = []
    for row_number, record in records:
        if (
            row_number in duplicate_emails
            or db.query(User).filter(User.email == record.email.lower()).first()
        ):
            conflicts.append({"row": row_number, "field": "email", "message": "Already registered or repeated in this file."})

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
                role=UserRole.FACULTY,
                phone=payload.phone,
                is_active=True,
            )
            db.add(user)
            db.flush()

            profile = FacultyProfile(
                user_id=user.id,
                department_id=department.id,
                designation=payload.designation.strip(),
                qualification=payload.qualification.strip(),
                specialization=payload.specialization.strip() if payload.specialization else None,
                office_room=payload.office_room.strip() if payload.office_room else None,
                joining_date=payload.joining_date,
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
    response_model=FacultyProfileOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register Faculty Account & Profile (Super Admin)"
)
def register_faculty(
    payload: FacultyRegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Registers a new faculty member with credentials and FacultyProfile
    (designation, qualification, specialization, office room).
    
    Restricted to: Super Admin.
    """
    clean_email = payload.email.lower().strip()
    if db.query(User).filter(User.email == clean_email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{clean_email}' is already registered."
        )

    department = resolve_enrollment_department(db, current_user, payload.department_id)

    # Create User login account
    user = User(
        email=clean_email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name.strip(),
        role=UserRole.FACULTY,
        phone=payload.phone,
        is_active=True
    )
    db.add(user)
    db.flush()

    # Create FacultyProfile
    profile = FacultyProfile(
        user_id=user.id,
        department_id=department.id,
        designation=payload.designation.strip(),
        qualification=payload.qualification.strip(),
        specialization=payload.specialization.strip() if payload.specialization else None,
        office_room=payload.office_room.strip() if payload.office_room else None,
        joining_date=payload.joining_date
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
# 2. List All Faculty Members
# ============================================================================
@router.get(
    "/",
    response_model=List[FacultyProfileOut],
    summary="List All Faculty Members"
)
def list_faculty_members(
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists all teaching faculty in the Computer Science department.
    Accessible to all authenticated users.
    """
    query = (
        db.query(FacultyProfile)
        .options(
            joinedload(FacultyProfile.user),
            joinedload(FacultyProfile.department),
        )
    )
    if current_user.role == UserRole.SUPER_ADMIN and department_id is not None:
        query = query.filter(FacultyProfile.department_id == department_id)
    elif current_user.role not in {UserRole.SUPER_ADMIN, UserRole.HOD}:
        query = query.filter(
            FacultyProfile.department_id == get_user_department_id(db, current_user)
        )
    return query.all()


# ============================================================================
# 3. Faculty Views Own Profile (/my-profile)
# ============================================================================
@router.get(
    "/my-profile",
    response_model=FacultyProfileOut,
    summary="Get Logged-in Faculty Profile"
)
def get_my_faculty_profile(
    faculty: FacultyProfile = Depends(get_current_faculty_profile),
    db: Session = Depends(get_db)
):
    """
    Retrieves the profile of the currently logged-in faculty member.
    Restricted to: Authenticated Faculty / HOD.
    """
    profile = (
        db.query(FacultyProfile)
        .filter(FacultyProfile.id == faculty.id)
        .options(
            joinedload(FacultyProfile.user),
            joinedload(FacultyProfile.department),
        )
        .first()
    )
    return profile


# ============================================================================
# 4. Get Faculty Profile by ID
# ============================================================================
@router.get(
    "/{faculty_id}",
    response_model=FacultyProfileOut,
    summary="Get Faculty Profile by ID"
)
def get_faculty_by_id(
    faculty_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves a faculty member profile by their ID.
    Accessible to all authenticated users.
    """
    faculty = (
        db.query(FacultyProfile)
        .filter(FacultyProfile.id == faculty_id)
        .options(
            joinedload(FacultyProfile.user),
            joinedload(FacultyProfile.department),
        )
        .first()
    )
    if not faculty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Faculty with ID {faculty_id} not found."
        )

    if current_user.role not in {UserRole.SUPER_ADMIN, UserRole.HOD}:
        require_department_access(db, current_user, faculty.department_id)
    return faculty
