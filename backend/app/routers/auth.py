"""
Authentication Router for Government Post Graduate College Mardan (GPGCM)
Computer Science Department Management System (Phase 1)

Endpoints:
- POST /api/v1/auth/login: JSON login (email + password) returning JWT access token
- POST /api/v1/auth/token: OAuth2 standard form login compatible with Swagger UI
- GET  /api/v1/auth/me: Returns current authenticated user and linked role profile
"""

import logging
from datetime import timedelta
from pathlib import Path
import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models.models import (
    User,
    UserRole,
    FacultyProfile,
    StudentProfile,
    Department
)
from app.schemas.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    SelfProfileUpdate,
    Token,
    UserOut,
)
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.deps import get_current_user, oauth2_scheme

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)

PROFILE_IMAGE_SIGNATURES = {
    ".png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    ".jpg": lambda data: data.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    ".gif": lambda data: data.startswith((b"GIF87a", b"GIF89a")),
    ".webp": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP",
}

# ============================================================================
# 1. JSON Login Endpoint (For React/Axios frontend)
# ============================================================================
@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="JSON Login (Email & Password)"
)
def login_json(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
) -> Token:
    """
    Authenticates user via standard JSON payload (email and password).
    
    Returns:
        Token: JWT Bearer access token, user role, user ID, full name, and email.
    
    Raises:
        HTTPException(401): If email does not exist or password hash mismatch.
        HTTPException(403): If the user account has been disabled by HOD / Admin.
    """
    # 1. Fetch user by email
    user = db.query(User).filter(User.email == credentials.email.lower().strip()).first()
    
    # 2. Verify credentials
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Check account active status
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is deactivated. Please contact the Computer Science Department HOD.",
        )

    # 4. Generate JWT access token with user id subject and role claim
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
        expires_delta=access_token_expires,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
    )


# ============================================================================
# 2. OAuth2 Password Form Login (For Swagger UI /docs Authorization)
# ============================================================================
@router.post(
    "/token",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="OAuth2 Form Login (Swagger UI)"
)
def login_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> Token:
    """
    OAuth2 Password Request Form endpoint compatible with FastAPI /docs 'Authorize' button.
    The 'username' field represents the college email address.
    """
    # 1. Query user by email
    user = db.query(User).filter(User.email == form_data.username.lower().strip()).first()
    
    # 2. Validate password
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Verify active status
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # 4. Generate JWT
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
        expires_delta=access_token_expires,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
    )


# ============================================================================
# 3. Current Authenticated User Profile Endpoint
# ============================================================================
@router.get(
    "/me",
    summary="Get Current User Profile & Role Info"
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retrieves the identity, role, and detailed profile of the currently logged-in user:
    - Base info: id, email, full_name, role, phone, is_active, created_at
    - If role == 'faculty' or 'hod': returns faculty_profile (designation, qualification, specialization, office_room, department)
    - If role == 'student': returns student_profile (roll_number, reg_number, session, semester, section, guardian info)
    - If role == 'super_admin': returns system administrator privileges
    """
    response_data: Dict[str, Any] = {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "phone": current_user.phone,
        "profile_image_url": current_user.profile_image_url,
        "department_id": None,
        "department_name": None,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "profile": None
    }

    # Fetch Department Name
    # Role: Faculty or HOD
    if current_user.role in [UserRole.FACULTY, UserRole.HOD]:
        faculty = (
            db.query(FacultyProfile)
            .filter(FacultyProfile.user_id == current_user.id)
            .first()
        )
        if faculty:
            department = db.query(Department).filter(
                Department.id == faculty.department_id
            ).first()
            response_data["department_id"] = faculty.department_id
            response_data["department_name"] = department.name if department else None
            response_data["profile"] = {
                "faculty_id": faculty.id,
                "department": department.name if department else None,
                "designation": faculty.designation,
                "qualification": faculty.qualification,
                "specialization": faculty.specialization,
                "office_room": faculty.office_room,
                "joining_date": faculty.joining_date.isoformat() if faculty.joining_date else None,
            }

    # Role: Student
    elif current_user.role == UserRole.STUDENT:
        student = (
            db.query(StudentProfile)
            .filter(StudentProfile.user_id == current_user.id)
            .first()
        )
        if student:
            department = db.query(Department).filter(
                Department.id == student.department_id
            ).first()
            response_data["department_id"] = student.department_id
            response_data["department_name"] = department.name if department else None
            response_data["profile"] = {
                "student_id": student.id,
                "department": department.name if department else None,
                "roll_number": student.roll_number,
                "reg_number": student.reg_number,
                "session": student.session,
                "semester": student.semester,
                "section": student.section,
                "program": student.program,
                "guardian_name": student.guardian_name,
                "guardian_phone": student.guardian_phone,
            }

    # Role: Super Admin
    elif current_user.role == UserRole.SUPER_ADMIN:
        response_data["profile"] = {
            "department": "College Administration",
            "scope": "Full System Access",
            "permissions": ["manage_users", "manage_faculty", "manage_students", "audit_logs"]
        }

    return response_data


@router.put(
    "/me",
    summary="Update Current User's Personal Profile"
)
def update_current_user_profile(
    payload: SelfProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    user_fields = {"email", "full_name", "phone"}
    profile_fields = set(updates) - user_fields

    if current_user.role == UserRole.STUDENT:
        allowed_profile_fields = {"guardian_name", "guardian_phone"}
        profile = db.query(StudentProfile).filter(
            StudentProfile.user_id == current_user.id
        ).first()
    elif current_user.role in [UserRole.FACULTY, UserRole.HOD]:
        allowed_profile_fields = {"qualification", "specialization", "office_room", "joining_date"}
        profile = db.query(FacultyProfile).filter(
            FacultyProfile.user_id == current_user.id
        ).first()
    else:
        allowed_profile_fields = set()
        profile = None

    prohibited_fields = profile_fields - allowed_profile_fields
    if prohibited_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"These profile fields cannot be updated for your role: {', '.join(sorted(prohibited_fields))}."
        )
    if profile_fields and profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A linked profile was not found for this account."
        )

    if "email" in updates:
        clean_email = str(updates["email"]).strip().lower()
        duplicate = db.query(User).filter(
            User.email == clean_email,
            User.id != current_user.id
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That email address is already in use."
            )
        current_user.email = clean_email
    if "full_name" in updates:
        full_name = updates["full_name"].strip()
        if not full_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Full name must not be empty."
            )
        current_user.full_name = full_name
    if "phone" in updates:
        current_user.phone = updates["phone"].strip() or None

    for field in profile_fields:
        value = updates[field]
        if isinstance(value, str):
            value = value.strip() or None
        setattr(profile, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The profile could not be saved because the email address is already in use."
        ) from exc
    db.refresh(current_user)
    if profile is not None:
        db.refresh(profile)
    return get_current_user_profile(current_user, db)


@router.post(
    "/me/profile-image",
    summary="Upload or replace the current user's profile image",
)
async def upload_profile_image(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Optional[str]]:
    extension = Path((image.filename or "").replace("\\", "/")).suffix.lower()
    signature_check = PROFILE_IMAGE_SIGNATURES.get(extension)
    if signature_check is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Profile images must be PNG, JPG, GIF, or WEBP files.",
        )

    image_bytes = await image.read(settings.MAX_PROFILE_IMAGE_SIZE_MB * 1024 * 1024 + 1)
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected profile image is empty.",
        )
    if len(image_bytes) > settings.MAX_PROFILE_IMAGE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Profile images are limited to {settings.MAX_PROFILE_IMAGE_SIZE_MB} MB.",
        )
    if not signature_check(image_bytes):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The selected file content does not match its image type.",
        )

    upload_directory = Path(settings.PROFILE_UPLOAD_DIR)
    filename = f"{uuid.uuid4().hex}{extension}"
    stored_path = upload_directory / filename
    try:
        upload_directory.mkdir(parents=True, exist_ok=True)
        stored_path.write_bytes(image_bytes)
    except OSError as exc:
        logger.exception("Could not store a profile image for user %s.", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not store the profile image.",
        ) from exc

    previous_url = current_user.profile_image_url
    current_user.profile_image_url = f"/uploads/profiles/{filename}"
    try:
        db.commit()
        db.refresh(current_user)
    except SQLAlchemyError as exc:
        db.rollback()
        try:
            stored_path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not clean up an uncommitted profile image for user %s.", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The profile image could not be saved.",
        ) from exc

    if previous_url:
        previous_path = (upload_directory / Path(previous_url).name).resolve()
        try:
            previous_path.relative_to(upload_directory.resolve())
            if previous_path != stored_path.resolve():
                previous_path.unlink(missing_ok=True)
        except ValueError:
            logger.warning("Ignoring an invalid previous profile image path for user %s.", current_user.id)
        except OSError:
            logger.exception("Could not remove the previous profile image for user %s.", current_user.id)

    return {"profile_image_url": current_user.profile_image_url}


@router.put(
    "/me/password",
    response_model=MessageResponse,
    summary="Change Current User's Password"
)
def change_current_user_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect."
        )
    if verify_password(payload.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be different from the current password."
        )

    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return MessageResponse(message="Password changed successfully.")
