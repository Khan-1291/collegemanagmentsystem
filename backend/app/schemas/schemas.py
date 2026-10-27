"""
Pydantic v2 Schemas for Government Post Graduate College Mardan (GPGCM)
Computer Science Department Management System (Phase 1)
Affiliated with Abdul Wali Khan University Mardan (AWKUM)
"""

from datetime import datetime, date
from typing import Optional, List, Any, Literal, Annotated
from pydantic import AfterValidator, BaseModel, EmailStr, Field, ConfigDict
from app.models.models import UserRole, AttendanceStatus, EnrollmentStatus


def validate_bcrypt_password_length(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 UTF-8 bytes.")
    return password


BcryptPassword = Annotated[str, AfterValidator(validate_bcrypt_password_length)]

# ==========================================
# Generic & Utility Schemas
# ==========================================
class MessageResponse(BaseModel):
    message: str
    success: bool = True
    details: Optional[Any] = None

# ==========================================
# Authentication & Token Schemas
# ==========================================
class LoginRequest(BaseModel):
    email: EmailStr
    password: BcryptPassword = Field(..., min_length=1, description="Plaintext password")

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    user_id: int
    full_name: str
    email: str

class TokenData(BaseModel):
    sub: Optional[str] = None      # Stores user ID as string
    role: Optional[str] = None     # Stores role enum value
    exp: Optional[int] = None      # Token expiration unix timestamp

# Alias for compatibility
TokenPayload = TokenData

# ==========================================
# User Schemas
# ==========================================
class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=120)
    role: UserRole = UserRole.STUDENT
    phone: Optional[str] = Field(None, max_length=25)
    is_active: bool = True

class UserCreate(UserBase):
    password: BcryptPassword = Field(..., min_length=6, description="Minimum 6 characters password")

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=120)
    phone: Optional[str] = Field(None, max_length=25)
    is_active: Optional[bool] = None
    password: Optional[BcryptPassword] = Field(None, min_length=6)

class SelfProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=120)
    phone: Optional[str] = Field(None, max_length=25)
    guardian_name: Optional[str] = Field(None, max_length=120)
    guardian_phone: Optional[str] = Field(None, max_length=25)
    qualification: Optional[str] = Field(None, max_length=120)
    specialization: Optional[str] = Field(None, max_length=150)
    office_room: Optional[str] = Field(None, max_length=50)
    joining_date: Optional[date] = None

    model_config = ConfigDict(extra="forbid")

class ChangePasswordRequest(BaseModel):
    current_password: BcryptPassword = Field(..., min_length=1)
    new_password: BcryptPassword = Field(..., min_length=6)

class UserStatusUpdate(BaseModel):
    is_active: bool

class UserOut(UserBase):
    id: int
    profile_image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityCommentOut(BaseModel):
    id: int
    activity_id: int
    author_id: int
    author_name: str
    author_role: UserRole
    profile_image_url: Optional[str] = None
    content: str
    created_at: datetime


class ActivityPostOut(BaseModel):
    id: int
    title: str
    content: str
    category: str
    author_id: int
    author_name: str
    author_role: UserRole
    profile_image_url: Optional[str] = None
    attachment_filename: Optional[str] = None
    attachment_content_type: Optional[str] = None
    created_at: datetime
    comments: List[ActivityCommentOut] = Field(default_factory=list)


class ActivityCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


ActivityCategory = Literal["Announcement", "Event", "Opportunity", "Workshop", "General"]

# ==========================================
# Department Schemas
# ==========================================
class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=2, max_length=20)
    description: Optional[str] = Field(None, max_length=2000)

class DepartmentCreate(DepartmentBase):
    hod_email: Optional[EmailStr] = None
    hod_password: Optional[BcryptPassword] = Field(None, min_length=6)
    hod_full_name: Optional[str] = Field(None, min_length=2, max_length=120)
    hod_phone: Optional[str] = Field(None, max_length=25)
    hod_designation: Optional[str] = Field(None, max_length=80)
    hod_qualification: Optional[str] = Field(None, max_length=120)

    model_config = ConfigDict(extra="forbid")


class DepartmentOut(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    hod_user_id: Optional[int] = None
    hod_name: Optional[str] = None
    hod_email: Optional[str] = None
    created_at: datetime


class DepartmentHODAssign(BaseModel):
    faculty_user_id: int

    model_config = ConfigDict(extra="forbid")

# ==========================================
# Faculty Profile Schemas
# ==========================================
class FacultyProfileBase(BaseModel):
    designation: str = Field(..., max_length=80, description="e.g. Assistant Professor, Lecturer")
    qualification: str = Field(..., max_length=120, description="e.g. MS Computer Science, Ph.D. AI")
    specialization: Optional[str] = Field(None, max_length=150)
    office_room: Optional[str] = Field(None, max_length=50)
    joining_date: Optional[date] = None

class FacultyProfileCreate(FacultyProfileBase):
    user_id: int
    department_id: Optional[int] = None

class FacultyProfileUpdate(BaseModel):
    designation: Optional[str] = Field(None, max_length=80)
    qualification: Optional[str] = Field(None, max_length=120)
    specialization: Optional[str] = Field(None, max_length=150)
    office_room: Optional[str] = Field(None, max_length=50)
    joining_date: Optional[date] = None

class FacultyDepartmentSummary(BaseModel):
    id: int
    name: str
    code: str

    model_config = ConfigDict(from_attributes=True)

class FacultyProfileOut(FacultyProfileBase):
    id: int
    user_id: int
    department_id: int
    department: Optional[FacultyDepartmentSummary] = None
    created_at: datetime
    updated_at: datetime
    user: Optional[UserOut] = None

    model_config = ConfigDict(from_attributes=True)

class FacultyRegisterRequest(BaseModel):
    department_id: Optional[int] = None
    email: EmailStr
    password: BcryptPassword = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=120)
    phone: Optional[str] = None
    designation: str = Field(..., min_length=1, max_length=80)
    qualification: str = Field(..., min_length=1, max_length=120)
    specialization: Optional[str] = None
    office_room: Optional[str] = None
    joining_date: Optional[date] = None

# ==========================================
# Student Profile Schemas
# ==========================================
class StudentProfileBase(BaseModel):
    roll_number: str = Field(..., max_length=50, description="College Roll No, e.g. CS-2022-01")
    reg_number: str = Field(..., max_length=80, description="AWKUM Reg No, e.g. AWKUM-CS-2022-101")
    session: str = Field(..., max_length=30, description="e.g. 2022-2026")
    semester: int = Field(..., ge=1, le=8, description="Semester between 1 and 8")
    section: str = Field("A", max_length=10)
    program: str = Field("BS Computer Science", max_length=100)
    guardian_name: Optional[str] = Field(None, max_length=120)
    guardian_phone: Optional[str] = Field(None, max_length=25)

class StudentProfileCreate(StudentProfileBase):
    user_id: int
    department_id: Optional[int] = None

class StudentProfileUpdate(BaseModel):
    session: Optional[str] = Field(None, max_length=30)
    semester: Optional[int] = Field(None, ge=1, le=8)
    section: Optional[str] = Field(None, max_length=10)
    guardian_name: Optional[str] = Field(None, max_length=120)
    guardian_phone: Optional[str] = Field(None, max_length=25)

class StudentProfileOut(StudentProfileBase):
    id: int
    user_id: int
    department_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    user: Optional[UserOut] = None

    model_config = ConfigDict(from_attributes=True)

class StudentRegisterRequest(BaseModel):
    department_id: Optional[int] = None
    email: EmailStr
    password: BcryptPassword = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=120)
    phone: Optional[str] = None
    roll_number: str = Field(..., min_length=1, max_length=50)
    reg_number: str = Field(..., min_length=1, max_length=80)
    session: str = Field(..., min_length=1, max_length=30)
    semester: int = Field(..., ge=1, le=8)
    section: str = "A"
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None

# ==========================================
# Subject Schemas
# ==========================================
class SubjectBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20, description="Course Code, e.g. CS-501")
    title: str = Field(..., min_length=1, max_length=150, description="Course Title, e.g. Software Engineering")
    credit_hours: int = Field(3, ge=1, le=6)
    semester: int = Field(..., ge=1, le=8)
    description: Optional[str] = None
    is_active: bool = True

class SubjectCreate(SubjectBase):
    department_id: Optional[int] = None

class SubjectUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=20)
    title: Optional[str] = Field(None, max_length=150)
    credit_hours: Optional[int] = Field(None, ge=1, le=6)
    semester: Optional[int] = Field(None, ge=1, le=8)
    description: Optional[str] = None
    is_active: Optional[bool] = None

class SubjectOut(SubjectBase):
    id: int
    department_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# Allocations & Enrollments
# ==========================================
class FacultySubjectCreate(BaseModel):
    faculty_id: int
    subject_id: int
    academic_session: str = Field(..., min_length=1, max_length=30, description="e.g. Fall 2024")
    section: str = Field("A", min_length=1, max_length=10)

class FacultySubjectOut(BaseModel):
    id: int
    faculty_id: int
    subject_id: int
    academic_session: str
    section: str
    created_at: datetime
    subject: Optional[SubjectOut] = None
    faculty: Optional[FacultyProfileOut] = None

    model_config = ConfigDict(from_attributes=True)

class StudentSubjectCreate(BaseModel):
    student_id: int
    subject_id: int
    academic_session: str = Field(..., description="e.g. Fall 2024")
    status: EnrollmentStatus = EnrollmentStatus.ENROLLED

class StudentBulkEnrollRequest(BaseModel):
    subject_id: int
    academic_session: str = Field(..., min_length=1, max_length=30)
    student_ids: List[int] = Field(..., min_length=1)

class StudentSubjectOut(BaseModel):
    id: int
    student_id: int
    subject_id: int
    academic_session: str
    status: EnrollmentStatus
    created_at: datetime
    subject: Optional[SubjectOut] = None
    student: Optional[StudentProfileOut] = None

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# Attendance Schemas
# ==========================================
class AttendanceCreate(BaseModel):
    subject_id: int
    student_id: int
    date: date
    status: AttendanceStatus = AttendanceStatus.PRESENT
    remarks: Optional[str] = Field(None, max_length=255)

class AttendanceRecordItem(BaseModel):
    student_id: int
    status: AttendanceStatus = AttendanceStatus.PRESENT
    remarks: Optional[str] = Field(None, max_length=255)

# Alias for router compatibility
AttendanceItem = AttendanceRecordItem

class AttendanceBulkCreate(BaseModel):
    subject_id: int
    date: date
    academic_session: str = Field(..., min_length=1, max_length=30)
    section: str = Field("A", min_length=1, max_length=10)
    records: List[AttendanceRecordItem] = Field(..., min_length=1)

# Alias for router compatibility
AttendanceBulkMarkRequest = AttendanceBulkCreate

class AttendanceOut(BaseModel):
    id: int
    subject_id: int
    faculty_id: int
    student_id: int
    academic_session: Optional[str] = None
    date: date
    status: AttendanceStatus
    remarks: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AttendanceStudentSummary(BaseModel):
    student_id: int
    roll_number: str
    full_name: str
    total_lectures: int
    present_count: int
    absent_count: int
    leave_count: int
    percentage: float
    calculated_attendance_marks: float  # Exact marks out of 5

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# Assignment Schemas
# ==========================================
class AssignmentCreate(BaseModel):
    subject_id: int
    academic_session: str = Field(..., min_length=1, max_length=30)
    title: str = Field(..., min_length=1, max_length=180)
    description: Optional[str] = None
    max_marks: float = Field(5.0, ge=5.0, le=5.0, description="The maximum is fixed at 5.0")
    due_date: datetime

class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=180)
    description: Optional[str] = None
    max_marks: Optional[float] = Field(None, ge=1.0, le=5.0)
    due_date: Optional[datetime] = None

class AssignmentOut(BaseModel):
    id: int
    subject_id: int
    faculty_id: int
    academic_session: str
    title: str
    description: Optional[str] = None
    max_marks: float
    due_date: datetime
    attachment_path: Optional[str] = None
    created_at: datetime
    submissions_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)

class AssignmentSubmissionCreate(BaseModel):
    assignment_id: int
    student_id: int
    file_path: str
    original_filename: str

class AssignmentSubmissionGrade(BaseModel):
    obtained_marks: float = Field(..., ge=0.0, le=5.0, description="Marks out of 5.0")
    feedback: Optional[str] = None

class AssignmentSubmissionOut(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    file_path: str
    original_filename: str
    submitted_at: datetime
    obtained_marks: Optional[float] = None
    feedback: Optional[str] = None
    graded_by: Optional[int] = None
    graded_at: Optional[datetime] = None
    student: Optional[StudentProfileOut] = None

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# Quiz Schemas
# ==========================================
class QuizCreate(BaseModel):
    subject_id: int
    academic_session: str = Field(..., min_length=1, max_length=30)
    title: str = Field(..., min_length=1, max_length=180)
    description: Optional[str] = None
    max_marks: float = Field(5.0, ge=5.0, le=5.0, description="The maximum is fixed at 5.0")
    quiz_date: date

class QuizOut(BaseModel):
    id: int
    subject_id: int
    faculty_id: int
    academic_session: str
    title: str
    description: Optional[str] = None
    max_marks: float
    quiz_date: date
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class QuizMarksCreate(BaseModel):
    quiz_id: int
    student_id: int
    obtained_marks: float = Field(..., ge=0.0, le=5.0, description="Marks obtained out of 5.0")
    remarks: Optional[str] = Field(None, max_length=255)

class QuizMarksItem(BaseModel):
    student_id: int
    obtained_marks: float = Field(..., ge=0.0, le=5.0)
    remarks: Optional[str] = None

class QuizMarksBulkCreate(BaseModel):
    marks: List[QuizMarksItem] = Field(..., min_length=1)

# Alias for compatibility
QuizMarksBulkRequest = QuizMarksBulkCreate

class QuizMarksOut(BaseModel):
    id: int
    quiz_id: int
    student_id: int
    obtained_marks: float
    remarks: Optional[str] = None
    entered_at: datetime
    student: Optional[StudentProfileOut] = None

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# Mid-Term Exam Marks (Max = 20)
# ==========================================
class MidTermMarksCreate(BaseModel):
    subject_id: int
    student_id: int
    academic_session: str
    obtained_marks: float = Field(..., ge=0.0, le=20.0, description="Marks obtained out of 20.0")
    remarks: Optional[str] = Field(None, max_length=255)

class MidTermMarksBulkItem(BaseModel):
    student_id: int
    obtained_marks: float = Field(..., ge=0.0, le=20.0)
    remarks: Optional[str] = None

class MidTermMarksBulkCreate(BaseModel):
    subject_id: int
    academic_session: str = Field(..., min_length=1, max_length=30)
    records: List[MidTermMarksBulkItem] = Field(..., min_length=1)

# Alias for compatibility
MidTermMarksBulkRequest = MidTermMarksBulkCreate

class MidTermMarksOut(BaseModel):
    id: int
    subject_id: int
    student_id: int
    faculty_id: int
    academic_session: str
    max_marks: float = 20.0
    obtained_marks: float
    remarks: Optional[str] = None
    created_at: datetime
    student: Optional[StudentProfileOut] = None

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# Presentation Marks (Max = 5)
# ==========================================
class PresentationMarksCreate(BaseModel):
    subject_id: int
    student_id: int
    academic_session: str
    topic: Optional[str] = Field(None, max_length=200)
    obtained_marks: float = Field(..., ge=0.0, le=5.0, description="Marks obtained out of 5.0")
    remarks: Optional[str] = Field(None, max_length=255)

class PresentationMarksBulkItem(BaseModel):
    student_id: int
    topic: Optional[str] = None
    obtained_marks: float = Field(..., ge=0.0, le=5.0)
    remarks: Optional[str] = None

class PresentationMarksBulkCreate(BaseModel):
    subject_id: int
    academic_session: str = Field(..., min_length=1, max_length=30)
    records: List[PresentationMarksBulkItem] = Field(..., min_length=1)

# Alias for compatibility
PresentationMarksBulkRequest = PresentationMarksBulkCreate

class PresentationMarksOut(BaseModel):
    id: int
    subject_id: int
    student_id: int
    faculty_id: int
    academic_session: str
    topic: Optional[str] = None
    max_marks: float = 5.0
    obtained_marks: float
    remarks: Optional[str] = None
    created_at: datetime
    student: Optional[StudentProfileOut] = None

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# Auto-Calculated Internal Result (Total 40 Marks)
# ==========================================
class InternalResultCalculateRequest(BaseModel):
    subject_id: int
    academic_session: str = Field(..., min_length=1, max_length=30)
    section: Optional[str] = Field(None, max_length=10)

class InternalResultOut(BaseModel):
    id: int
    subject_id: int
    student_id: int
    academic_session: str
    mid_paper_marks: float = Field(..., ge=0.0, le=20.0, description="Mid paper marks (max 20)")
    assignment_marks: float = Field(..., ge=0.0, le=5.0, description="Assignment marks (max 5)")
    quiz_marks: float = Field(..., ge=0.0, le=5.0, description="Quiz marks (max 5)")
    presentation_marks: float = Field(..., ge=0.0, le=5.0, description="Presentation marks (max 5)")
    attendance_marks: float = Field(..., ge=0.0, le=5.0, description="Attendance marks (max 5)")
    total_internal: float = Field(..., ge=0.0, le=40.0, description="Sum of 5 criteria (max 40)")
    attendance_percentage: float
    total_lectures: int
    attended_lectures: int
    is_finalized: bool
    remarks: Optional[str] = None
    generated_at: datetime
    updated_at: datetime
    student: Optional[StudentProfileOut] = None
    subject: Optional[SubjectOut] = None

    model_config = ConfigDict(from_attributes=True)

class SubjectResultSummary(BaseModel):
    subject_id: int
    subject_title: str
    subject_code: str
    academic_session: str
    total_students: int
    average_internal_marks: float
    highest_marks: float
    lowest_marks: float
    results: List[InternalResultOut]

    model_config = ConfigDict(from_attributes=True)

class FinalizeResultRequest(BaseModel):
    subject_id: int
    academic_session: str
    remarks: Optional[str] = Field(None, max_length=255, description="Official approval remarks")
