"""
Main Application Entry Point for Government Post Graduate College Mardan (GPGCM)
Computer Science Department Management System (Phase 1)
Affiliated with Abdul Wali Khan University Mardan (AWKUM), Pakistan

Final Year Project (FYP) Backend:
- Framework: FastAPI + SQLAlchemy + Alembic + PostgreSQL
- Authentication: OAuth2 with JWT (python-jose + passlib)
- Role-Based Access Control: super_admin, hod, faculty, student
- Core Modules: Authentication, Profiles, Subject Allocations, Attendance,
  Assignments (with file uploads), Quizzes, Mid-Term (20), Presentation (5),
  and Auto-Calculated 40-Mark Internal Results.
"""

import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

# Import all 9 routers
from app.routers import (
    auth,
    activities,
    departments,
    students,
    faculty,
    users,
    subjects,
    attendance,
    assignments,
    quizzes,
    marks,
    results
)

# ============================================================================
# Application Lifespan (Startup & Shutdown Hooks)
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize runtime directories. Database schema is prepared before startup
    by the deployment bootstrap and Alembic migration command.
    """
    # Ensure upload subdirectories exist
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "assignments"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "submissions"), exist_ok=True)
    os.makedirs(settings.PROFILE_UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.ACTIVITY_UPLOAD_DIR, exist_ok=True)
    
    yield
    # Shutdown logic (if any cleanup is required)


# ============================================================================
# FastAPI App Initialization with OpenAPI Metadata
# ============================================================================
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
## Government Post Graduate College Mardan (GPGCM)
### Computer Science Department Management System — Phase 1
**Affiliated with Abdul Wali Khan University Mardan (AWKUM), Pakistan**

---

### Core Academic Regulations (Phase 1):
- **Mid-Term Examination** : 20 Marks
- **Assignments**          : 05 Marks (Student file upload + Faculty grading)
- **Quizzes**              : 05 Marks (Classroom assessment tests)
- **Presentation**         : 05 Marks (Seminar / Project defense)
- **Attendance**           : 05 Marks (Exact AWKUM slab formula)
- **Total Internal Result**: **40 Marks**

### Attendance Marks Grading Slab:
- **≥ 90%**   → 5.0 Marks
- **80 – 89%** → 4.0 Marks
- **75 – 79%** → 3.0 Marks
- **70 – 74%** → 2.0 Marks
- **65 – 69%** → 1.0 Mark
- **< 65%**    → 0.0 Marks *(Barred from final AWKUM examination)*

---
*Note: Admission is handled by Higher Education Department (HED) and Fees by AWKUM.*
""",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# ============================================================================
# CORS Middleware Configuration
# ============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Static Files Mount for Assignment Uploads & Submissions
# ============================================================================
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount(
    "/uploads",
    StaticFiles(directory=settings.UPLOAD_DIR),
    name="uploads"
)

# ============================================================================
# Router Registration (All under /api/v1)
# ============================================================================
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(activities.router, prefix=settings.API_V1_STR)
app.include_router(departments.router, prefix=settings.API_V1_STR)
app.include_router(students.router, prefix=settings.API_V1_STR)
app.include_router(faculty.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(subjects.router, prefix=settings.API_V1_STR)
app.include_router(attendance.router, prefix=settings.API_V1_STR)
app.include_router(assignments.router, prefix=settings.API_V1_STR)
app.include_router(quizzes.router, prefix=settings.API_V1_STR)
app.include_router(marks.router, prefix=settings.API_V1_STR)
app.include_router(results.router, prefix=settings.API_V1_STR)


# ============================================================================
# Health & Root Endpoints
# ============================================================================
@app.get(
    "/",
    tags=["Health & Status"],
    summary="Institution Information & System Details"
)
def root():
    """
    Returns high-level institution, department, and examination structure details.
    """
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "college": {
            "name": settings.COLLEGE_NAME,
            "abbreviation": "GPGCM",
            "city": "Mardan, Khyber Pakhtunkhwa, Pakistan",
            "affiliation": settings.AFFILIATED_UNIVERSITY
        },
        "department": {
            "name": settings.DEPARTMENT_NAME,
            "code": "CS",
            "degree_program": "BS Computer Science (4-Year / 8-Semester)"
        },
        "internal_marks_distribution": {
            "mid_term_exam": 20.0,
            "assignments": 5.0,
            "quizzes": 5.0,
            "presentation": 5.0,
            "attendance": 5.0,
            "total_internal_marks": 40.0
        },
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_json": "/openapi.json"
        }
    }


@app.get(
    "/health",
    tags=["Health & Status"],
    summary="Health Check Probe"
)
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint for container probes, uptime monitoring, and dev validation.
    """
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc

    return {
        "status": "healthy",
        "database": "connected",
        "service": "gpgcm-cms-backend"
    }
