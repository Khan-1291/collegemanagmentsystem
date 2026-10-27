import html

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_hod_or_admin
from app.database import get_db
from app.models.models import FacultyProfile, StudentProfile, User, UserRole
from app.core.deps import require_department_access
from app.schemas.schemas import UserStatusUpdate
from app.services.email_service import queue_email

router = APIRouter(prefix="/users", tags=["User Management"])


@router.patch(
    "/{user_id}/status",
    summary="Activate or Deactivate a Student or Faculty Account (HOD / Admin)"
)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hod_or_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )
    if user.role not in {UserRole.STUDENT, UserRole.FACULTY}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only student and faculty accounts can be managed here."
        )
    if current_user.role == UserRole.HOD and user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HODs can manage student accounts only.",
        )
    profile_model = StudentProfile if user.role == UserRole.STUDENT else FacultyProfile
    profile = db.query(profile_model).filter(profile_model.user_id == user.id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The account's department profile was not found.",
        )
    if user.role == UserRole.STUDENT:
        require_department_access(db, current_user, profile.department_id)

    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    if not user.is_active:
        queue_email(
            background_tasks,
            user.email,
            "Your GPGCM portal account was deactivated",
            "Account access update",
            [
                f"Dear {html.escape(user.full_name)},",
                "Your GPGCM portal account has been deactivated. You can no longer sign in.",
                "Contact the Computer Science Department administrator if you believe this change was made in error.",
            ],
        )
    return {
        "user_id": user.id,
        "role": user.role.value,
        "is_active": user.is_active,
        "message": f"Account {'activated' if user.is_active else 'deactivated'} successfully."
    }
