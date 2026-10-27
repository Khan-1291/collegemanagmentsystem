"""Store attendance against an academic session.

Revision ID: 20261016_01
Revises:
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20261016_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("attendance"):
        return

    columns = {column["name"] for column in inspector.get_columns("attendance")}
    if "academic_session" not in columns:
        op.add_column(
            "attendance",
            sa.Column("academic_session", sa.String(length=30), nullable=True),
        )

    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("attendance")
        if constraint["name"]
    }
    with op.batch_alter_table("attendance") as batch_op:
        if "uq_student_subject_date_attendance" in unique_constraints:
            batch_op.drop_constraint(
                "uq_student_subject_date_attendance",
                type_="unique",
            )
        if "uq_student_subject_session_date_attendance" not in unique_constraints:
            batch_op.create_unique_constraint(
                "uq_student_subject_session_date_attendance",
                ["subject_id", "student_id", "academic_session", "date"],
            )

    if inspector.has_table("student_subjects"):
        session_rows = bind.execute(
            sa.text(
                "SELECT subject_id, student_id, MIN(academic_session) AS academic_session "
                "FROM student_subjects "
                "GROUP BY subject_id, student_id "
                "HAVING COUNT(DISTINCT academic_session) = 1"
            )
        ).mappings()
        sessions = {
            (row["subject_id"], row["student_id"]): row["academic_session"]
            for row in session_rows
        }
        for (subject_id, student_id), academic_session in sessions.items():
            bind.execute(
                sa.text(
                    "UPDATE attendance SET academic_session = :academic_session "
                    "WHERE subject_id = :subject_id AND student_id = :student_id "
                    "AND academic_session IS NULL"
                ),
                {
                    "academic_session": academic_session,
                    "subject_id": subject_id,
                    "student_id": student_id,
                },
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("attendance"):
        return
    columns = {column["name"] for column in inspector.get_columns("attendance")}
    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("attendance")
        if constraint["name"]
    }
    with op.batch_alter_table("attendance") as batch_op:
        if "uq_student_subject_session_date_attendance" in unique_constraints:
            batch_op.drop_constraint(
                "uq_student_subject_session_date_attendance",
                type_="unique",
            )
        if "uq_student_subject_date_attendance" not in unique_constraints:
            batch_op.create_unique_constraint(
                "uq_student_subject_date_attendance",
                ["subject_id", "student_id", "date"],
            )
        if "academic_session" in columns:
            batch_op.drop_column("academic_session")
