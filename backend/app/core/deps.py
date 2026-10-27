from typing import Generator, List, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.models import User, UserRole, FacultyProfile, StudentProfile
from app.schemas.schemas import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token"
)

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Decodes the JWT token from Bearer header and retrieves the User from database.
    Raises 401 if token is invalid or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    """
    Role-based Access Control dependency generator.
    Usage: Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HOD))
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {[r.value for r in allowed_roles]}, current: {current_user.role.value}"
            )
        return current_user
    return role_checker


def get_user_department_id(db: Session, user: User) -> int:
    if user.role in {UserRole.HOD, UserRole.FACULTY}:
        profile = db.query(FacultyProfile).filter(FacultyProfile.user_id == user.id).first()
    elif user.role == UserRole.STUDENT:
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not scoped to a department.",
        )
    if profile is None or profile.department_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not assigned to a department.",
        )
    return profile.department_id


def require_department_access(
    db: Session,
    user: User,
    department_id: int,
) -> None:
    if user.role == UserRole.SUPER_ADMIN:
        return
    if get_user_department_id(db, user) != department_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested record was not found.",
        )


def resolve_department_id(
    db: Session,
    user: User,
    requested_department_id: int | None,
    default_department_id: int | None = None,
) -> int:
    if user.role == UserRole.SUPER_ADMIN:
        department_id = requested_department_id or default_department_id
        if department_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A department must be selected.",
            )
    else:
        department_id = get_user_department_id(db, user)
        if requested_department_id is not None and requested_department_id != department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can create records only in your assigned department.",
            )

    from app.models.models import Department
    if db.query(Department.id).filter(Department.id == department_id).first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {department_id} not found.",
        )
    return department_id

# Pre-defined convenience role dependencies
require_super_admin = require_roles(UserRole.SUPER_ADMIN)
require_hod_or_admin = require_roles(UserRole.SUPER_ADMIN, UserRole.HOD)
require_hod_only = require_roles(UserRole.HOD)
require_faculty_or_admin = require_roles(UserRole.SUPER_ADMIN, UserRole.HOD, UserRole.FACULTY)
require_faculty_only = require_roles(UserRole.FACULTY)
require_student = require_roles(UserRole.STUDENT)

def get_current_faculty_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FacultyProfile:
    """
    Ensures current user is faculty (or admin) and returns their FacultyProfile record.
    """
    if current_user.role not in [UserRole.FACULTY, UserRole.HOD, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only faculty members can perform this action"
        )
    profile = db.query(FacultyProfile).filter(FacultyProfile.user_id == current_user.id).first()
    if not profile and current_user.role == UserRole.FACULTY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty profile not found for this user account"
        )
    return profile

def get_current_student_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StudentProfile:
    """
    Ensures current user is a student and returns their StudentProfile record.
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can perform this action"
        )
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found for this user account"
        )
    return profile
