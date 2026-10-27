from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.models import (
    EnrollmentStatus,
    FacultyProfile,
    FacultySubject,
    StudentProfile,
    StudentSubject,
    Subject,
    User,
    UserRole,
)
from app.core.deps import require_department_access


def require_subject_department_access(
    db: Session,
    current_user: User,
    subject_id: int,
) -> Subject:
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} not found.",
        )
    if current_user.role == UserRole.FACULTY:
        faculty = db.query(FacultyProfile).filter(
            FacultyProfile.user_id == current_user.id
        ).first()
        if faculty is None or db.query(FacultySubject.id).filter(
            FacultySubject.faculty_id == faculty.id,
            FacultySubject.subject_id == subject_id,
        ).first() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The requested record was not found.",
            )
    else:
        require_department_access(db, current_user, subject.department_id)
    return subject


def require_faculty_subject_allocation(
    db: Session,
    current_user: User,
    subject_id: int,
    academic_session: str | None = None,
    section: str | None = None,
) -> FacultyProfile | None:
    require_subject_department_access(db, current_user, subject_id)
    if current_user.role != UserRole.FACULTY:
        return None

    faculty = db.query(FacultyProfile).filter(
        FacultyProfile.user_id == current_user.id
    ).first()
    if faculty is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A faculty profile is required to use academic tools."
        )

    allocation_query = db.query(FacultySubject).filter(
        FacultySubject.faculty_id == faculty.id,
        FacultySubject.subject_id == subject_id,
    )
    if academic_session is not None:
        allocation_query = allocation_query.filter(
            FacultySubject.academic_session == academic_session.strip()
        )
    if section is not None:
        allocation_query = allocation_query.filter(
            FacultySubject.section == section.strip().upper()
        )
    if allocation_query.first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This subject is not allocated to your account for the selected academic session and section."
        )
    return faculty


def get_allocated_sections(
    db: Session,
    current_user: User,
    subject_id: int,
    academic_session: str,
) -> set[str] | None:
    require_subject_department_access(db, current_user, subject_id)
    pairs = get_faculty_allocation_pairs(
        db, current_user, subject_id, academic_session
    )
    if pairs is None:
        return None
    return {section for _, section in pairs}


def get_faculty_allocation_pairs(
    db: Session,
    current_user: User,
    subject_id: int,
    academic_session: str | None = None,
) -> set[tuple[str, str]] | None:
    require_subject_department_access(db, current_user, subject_id)
    if current_user.role != UserRole.FACULTY:
        return None
    faculty = require_faculty_subject_allocation(
        db, current_user, subject_id, academic_session
    )
    if faculty is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A faculty profile is required to use academic tools."
        )
    return {
        (session, section)
        for session, section in db.query(
            FacultySubject.academic_session,
            FacultySubject.section
        ).filter(
            FacultySubject.faculty_id == faculty.id,
            FacultySubject.subject_id == subject_id,
            *(
                [FacultySubject.academic_session == academic_session.strip()]
                if academic_session is not None
                else []
            ),
        ).all()
    }


def require_enrolled_students(
    db: Session,
    current_user: User,
    subject_id: int,
    academic_session: str,
    student_ids: set[int],
) -> None:
    require_subject_department_access(db, current_user, subject_id)
    if not student_ids:
        return

    query = (
        db.query(StudentProfile.id)
        .join(User, StudentProfile.user_id == User.id)
        .join(StudentSubject, StudentSubject.student_id == StudentProfile.id)
        .filter(
            StudentSubject.subject_id == subject_id,
            StudentSubject.academic_session == academic_session.strip(),
            StudentSubject.status == EnrollmentStatus.ENROLLED,
            StudentProfile.id.in_(student_ids),
            User.is_active.is_(True),
        )
    )
    if current_user.role == UserRole.FACULTY:
        faculty = db.query(FacultyProfile).filter(
            FacultyProfile.user_id == current_user.id
        ).first()
        if faculty is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A faculty profile is required to use academic tools."
            )
        sections = {
            section for (section,) in db.query(FacultySubject.section).filter(
                FacultySubject.faculty_id == faculty.id,
                FacultySubject.subject_id == subject_id,
                FacultySubject.academic_session == academic_session.strip(),
            ).all()
        }
        query = query.filter(StudentProfile.section.in_(sections))

    eligible_ids = {student_id for (student_id,) in query.all()}
    invalid_ids = sorted(student_ids - eligible_ids)
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Student profile(s) {', '.join(map(str, invalid_ids))} are not active and enrolled in this subject and academic session."
        )


def require_student_subject_enrollment(
    db: Session,
    current_user: User,
    subject_id: int,
    academic_session: str,
) -> None:
    require_subject_department_access(db, current_user, subject_id)
    if current_user.role != UserRole.STUDENT:
        return

    student_id = db.query(StudentProfile.id).filter(
        StudentProfile.user_id == current_user.id
    ).scalar()
    if student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A student profile is required to view enrolled course work."
        )

    enrollment = (
        db.query(StudentSubject.id)
        .join(Subject, StudentSubject.subject_id == Subject.id)
        .filter(
            StudentSubject.student_id == student_id,
            StudentSubject.subject_id == subject_id,
            StudentSubject.academic_session == academic_session.strip(),
            StudentSubject.status == EnrollmentStatus.ENROLLED,
            Subject.is_active.is_(True),
        )
        .first()
    )
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not actively enrolled in this subject for the selected academic session."
        )
