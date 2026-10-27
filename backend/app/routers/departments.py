from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, get_user_department_id, require_super_admin
from app.core.security import get_password_hash
from app.database import get_db
from app.models.models import Department, FacultyProfile, User, UserRole
from app.schemas.schemas import DepartmentCreate, DepartmentHODAssign, DepartmentOut
from app.services.email_service import queue_welcome_email

router = APIRouter(prefix="/departments", tags=["Departments"])


def serialize_department(department: Department) -> DepartmentOut:
    return DepartmentOut(
        id=department.id,
        name=department.name,
        code=department.code,
        description=department.description,
        hod_user_id=department.hod_user_id,
        hod_name=department.hod.full_name if department.hod else None,
        hod_email=department.hod.email if department.hod else None,
        created_at=department.created_at,
    )


@router.get("/", response_model=list[DepartmentOut], summary="List accessible departments")
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Department).options(joinedload(Department.hod))
    if current_user.role == UserRole.SUPER_ADMIN:
        departments = query.order_by(Department.name.asc()).all()
    else:
        department_id = get_user_department_id(db, current_user)
        departments = query.filter(Department.id == department_id).all()
    return [serialize_department(department) for department in departments]


@router.post(
    "/",
    response_model=DepartmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a department and optionally its HOD",
)
def create_department(
    payload: DepartmentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    name = payload.name.strip()
    code = payload.code.strip().upper()
    if not name or not code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Department name and code must not be empty.",
        )

    hod_fields = (
        payload.hod_email,
        payload.hod_password,
        payload.hod_full_name,
        payload.hod_designation,
        payload.hod_qualification,
    )
    if any(hod_fields) and not all(hod_fields):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="To create an HOD with a department, provide email, password, full name, designation, and qualification.",
        )
    if payload.hod_email and not all(
        value and value.strip()
        for value in (
            payload.hod_full_name,
            payload.hod_designation,
            payload.hod_qualification,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="HOD name, designation, and qualification must not be blank.",
        )

    department = Department(name=name, code=code, description=payload.description)
    db.add(department)
    try:
        db.flush()
        if payload.hod_email:
            clean_email = str(payload.hod_email).strip().lower()
            if db.query(User.id).filter(User.email == clean_email).first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The HOD email address is already registered.",
                )
            hod = User(
                email=clean_email,
                hashed_password=get_password_hash(payload.hod_password),
                full_name=payload.hod_full_name.strip(),
                phone=payload.hod_phone.strip() if payload.hod_phone else None,
                role=UserRole.HOD,
                is_active=True,
            )
            db.add(hod)
            db.flush()
            profile = FacultyProfile(
                user_id=hod.id,
                department_id=department.id,
                designation=payload.hod_designation.strip(),
                qualification=payload.hod_qualification.strip(),
            )
            db.add(profile)
            department.hod_user_id = hod.id
        db.commit()
        db.refresh(department)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A department with that name, code, or HOD account already exists.",
        ) from exc

    if payload.hod_email:
        queue_welcome_email(
            background_tasks,
            str(payload.hod_email).strip().lower(),
            payload.hod_full_name.strip(),
            payload.hod_password,
        )
    return serialize_department(department)


@router.patch(
    "/{department_id}/hod",
    response_model=DepartmentOut,
    summary="Assign an existing department faculty member as HOD",
)
def assign_department_hod(
    department_id: int,
    payload: DepartmentHODAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    department = (
        db.query(Department)
        .options(joinedload(Department.hod))
        .filter(Department.id == department_id)
        .first()
    )
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found.")

    faculty = (
        db.query(FacultyProfile)
        .join(User, FacultyProfile.user_id == User.id)
        .filter(
            FacultyProfile.user_id == payload.faculty_user_id,
            User.is_active.is_(True),
        )
        .first()
    )
    if faculty is None or faculty.department_id != department.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select an existing faculty account assigned to this department.",
        )
    user = db.query(User).filter(User.id == faculty.user_id).first()
    if user is None or user.role not in {UserRole.FACULTY, UserRole.HOD}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only an existing faculty account can be assigned as HOD.",
        )
    other_assignment = (
        db.query(Department)
        .filter(Department.hod_user_id == user.id, Department.id != department.id)
        .first()
    )
    if other_assignment is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is already assigned as HOD of another department.",
        )

    previous_hod = db.query(User).filter(User.id == department.hod_user_id).first()
    if previous_hod is not None and previous_hod.id != user.id:
        previous_hod.role = UserRole.FACULTY
    user.role = UserRole.HOD
    department.hod_user_id = user.id
    db.commit()
    db.refresh(department)
    return serialize_department(department)
