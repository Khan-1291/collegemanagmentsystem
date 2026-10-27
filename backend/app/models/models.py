import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Enum,
    Text,
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base

# ==========================================
# Enums
# ==========================================
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    HOD = "hod"
    FACULTY = "faculty"
    STUDENT = "student"

class AttendanceStatus(str, enum.Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    LEAVE = "Leave"

class EnrollmentStatus(str, enum.Enum):
    ENROLLED = "enrolled"
    DROPPED = "dropped"
    COMPLETED = "completed"

# ==========================================
# Core User & Department Models
# ==========================================
class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, default="Computer Science")
    code = Column(String(20), nullable=False, unique=True, default="CS")
    description = Column(Text, nullable=True)
    hod_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    faculty_profiles = relationship("FacultyProfile", back_populates="department")
    student_profiles = relationship("StudentProfile", back_populates="department")
    subjects = relationship("Subject", back_populates="department")
    hod = relationship("User", foreign_keys=[hod_user_id])


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.STUDENT, index=True)
    phone = Column(String(25), nullable=True)
    profile_image_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # One-to-one profile relationships
    faculty_profile = relationship("FacultyProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    student_profile = relationship("StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    activity_posts = relationship("ActivityPost", back_populates="author", cascade="all, delete-orphan")
    activity_comments = relationship("ActivityComment", back_populates="author", cascade="all, delete-orphan")


class ActivityPost(Base):
    __tablename__ = "activity_posts"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(30), nullable=False, default="General", index=True)
    attachment_storage_key = Column(String(255), nullable=True)
    attachment_filename = Column(String(255), nullable=True)
    attachment_content_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    author = relationship("User", back_populates="activity_posts")
    comments = relationship(
        "ActivityComment",
        back_populates="activity",
        cascade="all, delete-orphan",
        order_by="ActivityComment.created_at",
    )


class ActivityComment(Base):
    __tablename__ = "activity_comments"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activity_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    activity = relationship("ActivityPost", back_populates="comments")
    author = relationship("User", back_populates="activity_comments")


# ==========================================
# Profile Models
# ==========================================
class FacultyProfile(Base):
    __tablename__ = "faculty_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    # Primary affiliation; teaching access across departments is represented by FacultySubject.
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False)
    designation = Column(String(80), nullable=False)  # Professor, Associate Prof, Assistant Prof, Lecturer
    qualification = Column(String(120), nullable=False)  # Ph.D., MS CS, M.Phil
    specialization = Column(String(150), nullable=True)
    office_room = Column(String(50), nullable=True)
    joining_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="faculty_profile")
    department = relationship("Department", back_populates="faculty_profiles")
    subject_allocations = relationship("FacultySubject", back_populates="faculty", cascade="all, delete-orphan")
    attendance_records = relationship("Attendance", back_populates="faculty")
    assignments_created = relationship("Assignment", back_populates="faculty")
    quizzes_created = relationship("Quiz", back_populates="faculty")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False)
    roll_number = Column(String(50), unique=True, index=True, nullable=False)
    reg_number = Column(String(80), unique=True, index=True, nullable=False)  # AWKUM Registration No.
    session = Column(String(30), nullable=False)  # e.g., "2022-2026"
    semester = Column(Integer, nullable=False)    # 1 to 8
    section = Column(String(10), nullable=False, default="A")
    program = Column(String(100), nullable=False, default="BS Computer Science")
    guardian_name = Column(String(120), nullable=True)
    guardian_phone = Column(String(25), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="student_profile")
    department = relationship("Department", back_populates="student_profiles")
    subject_enrollments = relationship("StudentSubject", back_populates="student", cascade="all, delete-orphan")
    attendance_records = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")
    assignment_submissions = relationship("AssignmentSubmission", back_populates="student", cascade="all, delete-orphan")
    quiz_marks = relationship("QuizMarks", back_populates="student", cascade="all, delete-orphan")
    mid_term_marks = relationship("MidTermMarks", back_populates="student", cascade="all, delete-orphan")
    presentation_marks = relationship("PresentationMarks", back_populates="student", cascade="all, delete-orphan")
    internal_results = relationship("InternalResult", back_populates="student", cascade="all, delete-orphan")


# ==========================================
# Subject & Course Allocation Models
# ==========================================
class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(20), unique=True, index=True, nullable=False)  # CS-301
    title = Column(String(150), nullable=False)                        # Data Structures & Algorithms
    credit_hours = Column(Integer, nullable=False, default=3)          # 3 or 4
    semester = Column(Integer, nullable=False)                         # 1 - 8
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    department = relationship("Department", back_populates="subjects")
    faculty_allocations = relationship("FacultySubject", back_populates="subject", cascade="all, delete-orphan")
    student_enrollments = relationship("StudentSubject", back_populates="subject", cascade="all, delete-orphan")
    attendance_records = relationship("Attendance", back_populates="subject", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="subject", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="subject", cascade="all, delete-orphan")
    mid_term_marks = relationship("MidTermMarks", back_populates="subject", cascade="all, delete-orphan")
    presentation_marks = relationship("PresentationMarks", back_populates="subject", cascade="all, delete-orphan")
    internal_results = relationship("InternalResult", back_populates="subject", cascade="all, delete-orphan")


class FacultySubject(Base):
    __tablename__ = "faculty_subjects"

    id = Column(Integer, primary_key=True, index=True)
    faculty_id = Column(Integer, ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    academic_session = Column(String(30), nullable=False)  # e.g., "Fall 2024" or "Spring 2025"
    section = Column(String(10), nullable=False, default="A")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("faculty_id", "subject_id", "academic_session", "section", name="uq_faculty_subject_session"),
    )

    # Relationships
    faculty = relationship("FacultyProfile", back_populates="subject_allocations")
    subject = relationship("Subject", back_populates="faculty_allocations")


class StudentSubject(Base):
    __tablename__ = "student_subjects"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    academic_session = Column(String(30), nullable=False)  # e.g., "Fall 2024"
    status = Column(Enum(EnrollmentStatus), default=EnrollmentStatus.ENROLLED, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "academic_session", name="uq_student_subject_session"),
    )

    # Relationships
    student = relationship("StudentProfile", back_populates="subject_enrollments")
    subject = relationship("Subject", back_populates="student_enrollments")


# ==========================================
# Attendance Model
# ==========================================
class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    faculty_id = Column(Integer, ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    academic_session = Column(String(30), nullable=True)
    date = Column(Date, nullable=False, index=True)
    status = Column(Enum(AttendanceStatus), nullable=False, default=AttendanceStatus.PRESENT)
    remarks = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "subject_id",
            "student_id",
            "academic_session",
            "date",
            name="uq_student_subject_session_date_attendance",
        ),
    )

    # Relationships
    subject = relationship("Subject", back_populates="attendance_records")
    faculty = relationship("FacultyProfile", back_populates="attendance_records")
    student = relationship("StudentProfile", back_populates="attendance_records")


# ==========================================
# Assignment & Submission Models
# ==========================================
class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    faculty_id = Column(Integer, ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False)
    academic_session = Column(String(30), nullable=False)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    max_marks = Column(Float, nullable=False, default=5.0)  # Standard 5 marks
    due_date = Column(DateTime, nullable=False)
    attachment_path = Column(String(255), nullable=True)   # Faculty uploaded brief/pdf
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    subject = relationship("Subject", back_populates="assignments")
    faculty = relationship("FacultyProfile", back_populates="assignments_created")
    submissions = relationship("AssignmentSubmission", back_populates="assignment", cascade="all, delete-orphan")


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    obtained_marks = Column(Float, nullable=True)  # Nullable until graded
    feedback = Column(Text, nullable=True)
    graded_by = Column(Integer, ForeignKey("faculty_profiles.id", ondelete="SET NULL"), nullable=True)
    graded_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student_submission"),
    )

    # Relationships
    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("StudentProfile", back_populates="assignment_submissions")


# ==========================================
# Quiz & Quiz Marks Models
# ==========================================
class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    faculty_id = Column(Integer, ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False)
    academic_session = Column(String(30), nullable=False)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    max_marks = Column(Float, nullable=False, default=5.0)  # Standard 5 marks
    quiz_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    subject = relationship("Subject", back_populates="quizzes")
    faculty = relationship("FacultyProfile", back_populates="quizzes_created")
    marks_entries = relationship("QuizMarks", back_populates="quiz", cascade="all, delete-orphan")


class QuizMarks(Base):
    __tablename__ = "quiz_marks"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    obtained_marks = Column(Float, nullable=False)
    remarks = Column(String(255), nullable=True)
    entered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("quiz_id", "student_id", name="uq_quiz_student_marks"),
    )

    # Relationships
    quiz = relationship("Quiz", back_populates="marks_entries")
    student = relationship("StudentProfile", back_populates="quiz_marks")


# ==========================================
# Mid-Term & Presentation Marks Models
# ==========================================
class MidTermMarks(Base):
    __tablename__ = "mid_term_marks"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    faculty_id = Column(Integer, ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False)
    academic_session = Column(String(30), nullable=False)
    max_marks = Column(Float, nullable=False, default=20.0)  # Exactly 20 marks
    obtained_marks = Column(Float, nullable=False)           # 0 to 20
    remarks = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("subject_id", "student_id", "academic_session", name="uq_mid_term_student_session"),
    )

    # Relationships
    subject = relationship("Subject", back_populates="mid_term_marks")
    student = relationship("StudentProfile", back_populates="mid_term_marks")


class PresentationMarks(Base):
    __tablename__ = "presentation_marks"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    faculty_id = Column(Integer, ForeignKey("faculty_profiles.id", ondelete="CASCADE"), nullable=False)
    academic_session = Column(String(30), nullable=False)
    topic = Column(String(200), nullable=True)
    max_marks = Column(Float, nullable=False, default=5.0)   # Exactly 5 marks
    obtained_marks = Column(Float, nullable=False)           # 0 to 5
    remarks = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("subject_id", "student_id", "academic_session", name="uq_presentation_student_session"),
    )

    # Relationships
    subject = relationship("Subject", back_populates="presentation_marks")
    student = relationship("StudentProfile", back_populates="presentation_marks")


# ==========================================
# Auto-Calculated Internal Result (Total 40 marks)
# ==========================================
class InternalResult(Base):
    __tablename__ = "internal_results"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    academic_session = Column(String(30), nullable=False)

    # 5 Components of Internal Marks Formula (Total = 40)
    mid_paper_marks = Column(Float, nullable=False, default=0.0)      # Out of 20
    assignment_marks = Column(Float, nullable=False, default=0.0)     # Out of 5
    quiz_marks = Column(Float, nullable=False, default=0.0)           # Out of 5
    presentation_marks = Column(Float, nullable=False, default=0.0)   # Out of 5
    attendance_marks = Column(Float, nullable=False, default=0.0)     # Out of 5
    total_internal = Column(Float, nullable=False, default=0.0)       # Out of 40

    # Attendance statistics
    total_lectures = Column(Integer, nullable=False, default=0)
    attended_lectures = Column(Integer, nullable=False, default=0)
    attendance_percentage = Column(Float, nullable=False, default=0.0)

    # Status & Audit
    is_finalized = Column(Boolean, default=False, nullable=False)
    remarks = Column(String(255), nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("subject_id", "student_id", "academic_session", name="uq_internal_result_student_session"),
    )

    # Relationships
    subject = relationship("Subject", back_populates="internal_results")
    student = relationship("StudentProfile", back_populates="internal_results")
