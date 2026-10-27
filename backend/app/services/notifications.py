import html
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.models import (
    EnrollmentStatus,
    StudentProfile,
    StudentSubject,
    User,
)
from app.services.email_service import queue_email


def enrolled_student_emails(
    db: Session,
    subject_id: int,
    academic_session: str,
    student_ids: set[int] | None = None,
) -> list[tuple[int, str, str]]:
    query = (
        db.query(StudentProfile.id, User.email, User.full_name)
        .join(User, StudentProfile.user_id == User.id)
        .join(StudentSubject, StudentSubject.student_id == StudentProfile.id)
        .filter(
            StudentSubject.subject_id == subject_id,
            StudentSubject.academic_session == academic_session,
            StudentSubject.status == EnrollmentStatus.ENROLLED,
            User.is_active.is_(True),
        )
    )
    if student_ids is not None:
        if not student_ids:
            return []
        query = query.filter(StudentProfile.id.in_(student_ids))
    return query.distinct().all()


def notify_class(
    background_tasks: BackgroundTasks,
    recipients: list[tuple[int, str, str]],
    subject_line: str,
    title: str,
    details: list[str],
) -> None:
    for _, email, full_name in recipients:
        paragraphs = [f"Dear {html.escape(full_name)},", *details]
        queue_email(background_tasks, email, subject_line, title, paragraphs)


def notify_student(
    background_tasks: BackgroundTasks,
    db: Session,
    student_id: int,
    subject_line: str,
    title: str,
    details: list[str],
) -> None:
    recipient = (
        db.query(User.email, User.full_name)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .filter(StudentProfile.id == student_id, User.is_active.is_(True))
        .first()
    )
    if recipient:
        notify_class(
            background_tasks,
            [(student_id, recipient.email, recipient.full_name)],
            subject_line,
            title,
            details,
        )
