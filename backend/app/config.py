import os
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "GPGCM College Management System - Phase 1 (CS Dept)"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    COLLEGE_NAME: str = "Government Post Graduate College Mardan (GPGCM)"
    AFFILIATED_UNIVERSITY: str = "Abdul Wali Khan Mardan (AWKUM)"
    DEPARTMENT_NAME: str = "Computer Science"

    DATABASE_URL: str
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    UPLOAD_DIR: str = "uploads"
    PROFILE_UPLOAD_DIR: str = "uploads/profiles"
    MAX_PROFILE_IMAGE_SIZE_MB: int = 5
    ACTIVITY_UPLOAD_DIR: str = "private_uploads/activities"
    MAX_FILE_SIZE_MB: int = 15
    MAX_ACTIVITY_ATTACHMENT_SIZE_MB: int = 10
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "GPGCM College <onboarding@resend.dev>"
    FRONTEND_BASE_URL: str = "http://localhost:5173"
    ALLOWED_EXTENSIONS: List[str] = [
        ".pdf",
        ".docx",
        ".zip",
        ".png",
        ".jpg",
        ".txt",
        ".py",
        ".cpp",
        ".java",
    ]

    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

os.makedirs(os.path.join(settings.UPLOAD_DIR, "assignments"), exist_ok=True)
os.makedirs(os.path.join(settings.UPLOAD_DIR, "submissions"), exist_ok=True)
os.makedirs(settings.PROFILE_UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.ACTIVITY_UPLOAD_DIR, exist_ok=True)
