from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import (
    Attendance,
    AttendanceStatus,
    EnrollmentStatus,
    Assignment,
    AssignmentSubmission,
    Quiz,
    QuizMarks,
    MidTermMarks,
    PresentationMarks,
    InternalResult,
    StudentProfile,
    StudentSubject
)

def calculate_attendance_marks(percentage: float) -> float:
    """
    Calculates attendance marks out of 5 based on GPGCM / AWKUM exact grading slab:
    - >= 90%      -> 5 marks
    - 80% - 89.9% -> 4 marks
    - 75% - 79.9% -> 3 marks
    - 70% - 74.9% -> 2 marks
    - 65% - 69.9% -> 1 mark
    - Below 65%   -> 0 marks
    """
    if percentage >= 90.0:
        return 5.0
    elif percentage >= 80.0:
        return 4.0
    elif percentage >= 75.0:
        return 3.0
    elif percentage >= 70.0:
        return 2.0
    elif percentage >= 65.0:
        return 1.0
    else:
        return 0.0

def calculate_student_internal_result(
    db: Session,
    subject_id: int,
    student_id: int,
    academic_session: str,
    save_to_db: bool = True
) -> InternalResult:
    """
    Auto-calculates the complete 40-mark internal result for a given student & subject.
    Formula:
      1. Mid Paper:    20 marks
      2. Assignment:    5 marks (scaled average of graded submissions)
      3. Quiz:          5 marks (scaled average of quizzes)
      4. Presentation:  5 marks
      5. Attendance:    5 marks (based on exact attendance percentage slab)
      Total Internal = 40 marks
    """
    # ----------------------------------------------------
    # 1. Mid Paper Marks (Out of 20)
    # ----------------------------------------------------
    mid_record = (
        db.query(MidTermMarks)
        .filter(
            MidTermMarks.subject_id == subject_id,
            MidTermMarks.student_id == student_id,
            MidTermMarks.academic_session == academic_session,
        )
        .first()
    )
    mid_paper_marks = round(float(mid_record.obtained_marks), 2) if mid_record else 0.0
    mid_paper_marks = min(max(mid_paper_marks, 0.0), 20.0)

    # ----------------------------------------------------
    # 2. Assignment Marks (Out of 5)
    # ----------------------------------------------------
    # Find all assignments for this subject & session
    assignments = (
        db.query(Assignment)
        .filter(
            Assignment.subject_id == subject_id,
            Assignment.academic_session == academic_session,
        )
        .all()
    )
    
    assignment_marks = 0.0
    if assignments:
        assignment_ids = [a.id for a in assignments]
        # Query graded submissions by this student
        submissions = (
            db.query(AssignmentSubmission)
            .filter(
                AssignmentSubmission.assignment_id.in_(assignment_ids),
                AssignmentSubmission.student_id == student_id,
                AssignmentSubmission.obtained_marks.isnot(None),
            )
            .all()
        )
        if submissions:
            # Calculate average percentage across all assignments and normalize to 5 marks
            # Alternatively, if each assignment max_marks = 5, average of obtained
            # Generic scale: (obtained / max) * 5.0
            ratios = []
            assignment_map = {a.id: a.max_marks for a in assignments}
            for sub in submissions:
                max_m = assignment_map.get(sub.assignment_id, 5.0)
                if max_m > 0:
                    ratios.append(sub.obtained_marks / max_m)
            
            if ratios:
                # Average performance across assignments scaled to 5
                assignment_marks = round((sum(ratios) / len(assignments)) * 5.0, 2)
    assignment_marks = min(max(assignment_marks, 0.0), 5.0)

    # ----------------------------------------------------
    # 3. Quiz Marks (Out of 5)
    # ----------------------------------------------------
    quizzes = (
        db.query(Quiz)
        .filter(
            Quiz.subject_id == subject_id,
            Quiz.academic_session == academic_session,
        )
        .all()
    )
    
    quiz_marks = 0.0
    if quizzes:
        quiz_ids = [q.id for q in quizzes]
        q_entries = (
            db.query(QuizMarks)
            .filter(
                QuizMarks.quiz_id.in_(quiz_ids),
                QuizMarks.student_id == student_id,
            )
            .all()
        )
        if q_entries:
            quiz_map = {q.id: q.max_marks for q in quizzes}
            ratios = []
            for entry in q_entries:
                max_m = quiz_map.get(entry.quiz_id, 5.0)
                if max_m > 0:
                    ratios.append(entry.obtained_marks / max_m)
            if ratios:
                quiz_marks = round((sum(ratios) / len(quizzes)) * 5.0, 2)
    quiz_marks = min(max(quiz_marks, 0.0), 5.0)

    # ----------------------------------------------------
    # 4. Presentation Marks (Out of 5)
    # ----------------------------------------------------
    pres_record = (
        db.query(PresentationMarks)
        .filter(
            PresentationMarks.subject_id == subject_id,
            PresentationMarks.student_id == student_id,
            PresentationMarks.academic_session == academic_session,
        )
        .first()
    )
    presentation_marks = round(float(pres_record.obtained_marks), 2) if pres_record else 0.0
    presentation_marks = min(max(presentation_marks, 0.0), 5.0)

    # ----------------------------------------------------
    # 5. Attendance Marks (Out of 5)
    # ----------------------------------------------------
    # Total unique class sessions conducted for this subject
    # Or total attendance entries for this student
    student_attendance = (
        db.query(Attendance)
        .filter(
            Attendance.subject_id == subject_id,
            Attendance.student_id == student_id,
            Attendance.academic_session == academic_session,
        )
        .all()
    )
    total_lectures = len(student_attendance)
    attended_lectures = sum(1 for a in student_attendance if a.status == AttendanceStatus.PRESENT)
    
    if total_lectures > 0:
        attendance_percentage = round((attended_lectures / total_lectures) * 100.0, 2)
    else:
        # If no attendance has been recorded yet
        attendance_percentage = 0.0
    
    attendance_marks = calculate_attendance_marks(attendance_percentage)

    # ----------------------------------------------------
    # Total Internal (Out of 40)
    # ----------------------------------------------------
    total_internal = round(
        mid_paper_marks + assignment_marks + quiz_marks + presentation_marks + attendance_marks,
        2
    )

    # Look up existing result or create new
    internal_res = (
        db.query(InternalResult)
        .filter(
            InternalResult.subject_id == subject_id,
            InternalResult.student_id == student_id,
            InternalResult.academic_session == academic_session,
        )
        .first()
    )

    if not internal_res:
        internal_res = InternalResult(
            subject_id=subject_id,
            student_id=student_id,
            academic_session=academic_session,
        )
        db.add(internal_res)

    internal_res.mid_paper_marks = mid_paper_marks
    internal_res.assignment_marks = assignment_marks
    internal_res.quiz_marks = quiz_marks
    internal_res.presentation_marks = presentation_marks
    internal_res.attendance_marks = attendance_marks
    internal_res.total_internal = total_internal
    internal_res.total_lectures = total_lectures
    internal_res.attended_lectures = attended_lectures
    internal_res.attendance_percentage = attendance_percentage

    if save_to_db:
        db.commit()
        db.refresh(internal_res)

    return internal_res

def calculate_subject_internal_results(
    db: Session,
    subject_id: int,
    academic_session: str,
    sections: set[str] | None = None,
) -> List[InternalResult]:
    """
    Calculates internal marks for all students enrolled in a subject for the given session.
    """
    enrollment_query = (
        db.query(StudentSubject)
        .filter(
            StudentSubject.subject_id == subject_id,
            StudentSubject.academic_session == academic_session,
            StudentSubject.status == EnrollmentStatus.ENROLLED,
        )
    )
    if sections is not None:
        enrollment_query = (
            enrollment_query
            .join(StudentProfile, StudentSubject.student_id == StudentProfile.id)
            .filter(StudentProfile.section.in_(sections))
        )
    enrollments = enrollment_query.all()
    
    results = []
    for enr in enrollments:
        res = calculate_student_internal_result(
            db=db,
            subject_id=subject_id,
            student_id=enr.student_id,
            academic_session=academic_session,
            save_to_db=False
        )
        results.append(res)
    
    db.commit()
    for res in results:
        db.refresh(res)
    return results
