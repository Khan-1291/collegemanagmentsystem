import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import settings
from app.core.deps import get_current_user
from app.database import get_db
from app.models.models import ActivityComment, ActivityPost, User, UserRole
from app.schemas.schemas import (
    ActivityCategory,
    ActivityCommentCreate,
    ActivityCommentOut,
    ActivityPostOut,
)

router = APIRouter(prefix="/activities", tags=["Department Activities"])
logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = {"Announcement", "Event", "Opportunity", "Workshop", "General"}
ALLOWED_ATTACHMENTS = {
    ".pdf": ("application/pdf", lambda data: data.startswith(b"%PDF-")),
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".gif": ("image/gif", lambda data: data.startswith((b"GIF87a", b"GIF89a"))),
    ".webp": (
        "image/webp",
        lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP",
    ),
}


def serialize_post(post: ActivityPost) -> ActivityPostOut:
    return ActivityPostOut(
        id=post.id,
        title=post.title,
        content=post.content,
        category=post.category,
        author_id=post.author_id,
        author_name=post.author.full_name,
        author_role=post.author.role,
        profile_image_url=post.author.profile_image_url,
        attachment_filename=post.attachment_filename,
        attachment_content_type=post.attachment_content_type,
        created_at=post.created_at,
        comments=[serialize_comment(comment) for comment in post.comments],
    )


def serialize_comment(comment: ActivityComment) -> ActivityCommentOut:
    return ActivityCommentOut(
        id=comment.id,
        activity_id=comment.activity_id,
        author_id=comment.author_id,
        author_name=comment.author.full_name,
        author_role=comment.author.role,
        profile_image_url=comment.author.profile_image_url,
        content=comment.content,
        created_at=comment.created_at,
    )


@router.get("/", response_model=list[ActivityPostOut], summary="List Department Activities")
def list_activities(
    category: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if category and category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Category must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}.",
        )

    query = db.query(ActivityPost).options(
        joinedload(ActivityPost.author),
        selectinload(ActivityPost.comments).joinedload(ActivityComment.author),
    )
    if category:
        query = query.filter(ActivityPost.category == category)
    posts = (
        query.order_by(ActivityPost.created_at.desc(), ActivityPost.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [serialize_post(post) for post in posts]


@router.get(
    "/{activity_id}/comments",
    response_model=list[ActivityCommentOut],
    summary="Get comments for a department activity",
)
def list_activity_comments(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    activity_exists = db.query(ActivityPost.id).filter(ActivityPost.id == activity_id).first()
    if activity_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")

    comments = (
        db.query(ActivityComment)
        .options(joinedload(ActivityComment.author))
        .filter(ActivityComment.activity_id == activity_id)
        .order_by(ActivityComment.created_at.asc(), ActivityComment.id.asc())
        .all()
    )
    return [serialize_comment(comment) for comment in comments]


@router.post(
    "/{activity_id}/comments",
    response_model=ActivityCommentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Comment on a department activity",
)
def create_activity_comment(
    activity_id: int,
    payload: ActivityCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    activity = db.query(ActivityPost).filter(ActivityPost.id == activity_id).first()
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")

    content = payload.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Comment content must not be blank.",
        )
    comment = ActivityComment(
        activity_id=activity_id,
        author_id=current_user.id,
        content=content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return serialize_comment(comment)


@router.delete(
    "/{activity_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
)
def delete_activity_comment(
    activity_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = (
        db.query(ActivityComment)
        .filter(
            ActivityComment.id == comment_id,
            ActivityComment.activity_id == activity_id,
        )
        .first()
    )
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")
    if comment.author_id != current_user.id and current_user.role not in {
        UserRole.FACULTY,
        UserRole.HOD,
        UserRole.SUPER_ADMIN,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can delete only your own comments.",
        )

    db.delete(comment)
    db.commit()
    return None


@router.post("/", response_model=ActivityPostOut, status_code=status.HTTP_201_CREATED)
async def create_activity(
    title: str = Form(..., min_length=1, max_length=180),
    content: str = Form(..., min_length=1, max_length=10000),
    category: ActivityCategory = Form("General"),
    attachment: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    title = title.strip()
    content = content.strip()
    if not title or not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Title and content must not be blank.",
        )

    storage_key = None
    original_filename = None
    content_type = None
    attachment_bytes = None
    if attachment and attachment.filename:
        extension = Path(attachment.filename.replace("\\", "/")).suffix.lower()
        attachment_type = ALLOWED_ATTACHMENTS.get(extension)
        if not attachment_type:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Attachments must be PDF, PNG, JPG, GIF, or WEBP files.",
            )
        attachment_bytes = await attachment.read(
            settings.MAX_ACTIVITY_ATTACHMENT_SIZE_MB * 1024 * 1024 + 1
        )
        if len(attachment_bytes) > settings.MAX_ACTIVITY_ATTACHMENT_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Activity attachments are limited to {settings.MAX_ACTIVITY_ATTACHMENT_SIZE_MB} MB.",
            )
        content_type, signature_check = attachment_type
        if not signature_check(attachment_bytes):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="The selected file content does not match its file type.",
            )
        storage_key = f"{uuid.uuid4().hex}{extension}"
        original_filename = Path(attachment.filename.replace("\\", "/")).name[:255]

    stored_path = None
    if attachment_bytes is not None and storage_key:
        upload_directory = Path(settings.ACTIVITY_UPLOAD_DIR)
        try:
            upload_directory.mkdir(parents=True, exist_ok=True)
            stored_path = upload_directory / storage_key
            stored_path.write_bytes(attachment_bytes)
        except OSError as exc:
            logger.exception("Could not store a department activity attachment.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not store the activity attachment.",
            ) from exc

    post = ActivityPost(
        author_id=current_user.id,
        title=title,
        content=content,
        category=category,
        attachment_storage_key=storage_key,
        attachment_filename=original_filename,
        attachment_content_type=content_type,
    )
    try:
        db.add(post)
        db.commit()
        db.refresh(post)
        db.refresh(current_user)
    except Exception:
        db.rollback()
        if stored_path:
            try:
                stored_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Could not clean up an uncommitted activity attachment.")
        raise

    return serialize_post(post)


@router.get("/{activity_id}/attachment", response_class=FileResponse)
def download_activity_attachment(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(ActivityPost).filter(ActivityPost.id == activity_id).first()
    if post is None or not post.attachment_storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")

    root = Path(settings.ACTIVITY_UPLOAD_DIR).resolve()
    path = (root / post.attachment_storage_key).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        logger.error("Activity %s has an invalid attachment storage key.", activity_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.") from exc
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file is unavailable.")

    return FileResponse(
        path,
        media_type=post.attachment_content_type or "application/octet-stream",
        filename=post.attachment_filename or "activity-attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(ActivityPost).filter(ActivityPost.id == activity_id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")

    if (
        current_user.role == UserRole.STUDENT
        and post.author_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students can delete only their own activity posts.",
        )

    storage_key = post.attachment_storage_key
    db.delete(post)
    db.commit()

    if storage_key:
        attachment_path = Path(settings.ACTIVITY_UPLOAD_DIR) / storage_key
        try:
            attachment_path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not remove the attachment for activity %s.", activity_id)

    return None
