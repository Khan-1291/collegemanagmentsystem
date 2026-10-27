"""Enforce department ownership and support department HODs.

Revision ID: 20261025_02
Revises: 20261025_01
Create Date: 2026-10-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20261025_02"
down_revision = "20261025_01"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("departments"):
        op.create_table(
            "departments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False, unique=True),
            sa.Column("code", sa.String(length=20), nullable=False, unique=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    inspector = sa.inspect(bind)
    if "hod_user_id" not in {column["name"] for column in inspector.get_columns("departments")}:
        op.add_column(
            "departments",
            sa.Column("hod_user_id", sa.Integer(), nullable=True),
        )
        with op.batch_alter_table("departments") as batch_op:
            batch_op.create_foreign_key(
                "fk_departments_hod_user_id_users",
                "users",
                ["hod_user_id"],
                ["id"],
                ondelete="SET NULL",
            )
    department_forekeys = sa.inspect(bind).get_foreign_keys("departments")
    if not any(
        foreign_key.get("constrained_columns") == ["hod_user_id"]
        and foreign_key.get("referred_table") == "users"
        for foreign_key in department_forekeys
    ):
        with op.batch_alter_table("departments") as batch_op:
            batch_op.create_foreign_key(
                "fk_departments_hod_user_id_users",
                "users",
                ["hod_user_id"],
                ["id"],
                ondelete="SET NULL",
            )
    inspector = sa.inspect(bind)
    unique_hod_index = any(
        index["name"] == "uq_departments_hod_user_id"
        and index.get("column_names") == ["hod_user_id"]
        for index in inspector.get_indexes("departments")
    )
    unique_hod_constraint = any(
        constraint.get("column_names") == ["hod_user_id"]
        for constraint in inspector.get_unique_constraints("departments")
    )
    if not unique_hod_index and not unique_hod_constraint:
        op.create_index(
            "uq_departments_hod_user_id",
            "departments",
            ["hod_user_id"],
            unique=True,
        )

    if not bind.execute(
        sa.text("SELECT id FROM departments WHERE code = 'CS' LIMIT 1")
    ).first():
        bind.execute(
            sa.text(
                "INSERT INTO departments (name, code, description, created_at) "
                "VALUES ('Computer Science', 'CS', 'Computer Science Department', CURRENT_TIMESTAMP)"
            )
        )
    cs_department_id = bind.execute(
        sa.text("SELECT id FROM departments WHERE code = 'CS' LIMIT 1")
    ).scalar_one()

    inspector = sa.inspect(bind)
    for table_name in ("student_profiles", "faculty_profiles", "subjects"):
        if inspector.has_table(table_name):
            bind.execute(
                sa.text(
                    f"UPDATE {table_name} SET department_id = :department_id "
                    f"WHERE department_id IS NULL OR NOT EXISTS "
                    f"(SELECT 1 FROM departments d WHERE d.id = {table_name}.department_id)"
                ),
                {"department_id": cs_department_id},
            )

    if inspector.has_table("faculty_profiles") and inspector.has_table("users"):
        faculty_columns = {column["name"] for column in inspector.get_columns("faculty_profiles")}
        required_columns = {"created_at", "updated_at"}
        if required_columns <= faculty_columns:
            bind.execute(
                sa.text(
                    "INSERT INTO faculty_profiles "
                    "(user_id, department_id, designation, qualification, created_at, updated_at) "
                    "SELECT u.id, :department_id, 'Head of Department', 'Not specified', "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM users u "
                    "WHERE u.role IN ('HOD') AND NOT EXISTS "
                    "(SELECT 1 FROM faculty_profiles f WHERE f.user_id = u.id)"
                ),
                {"department_id": cs_department_id},
            )

        hod_user = bind.execute(
            sa.text(
                "SELECT u.id FROM users u "
                "JOIN faculty_profiles f ON f.user_id = u.id "
                "WHERE u.role IN ('HOD') AND f.department_id = :department_id "
                "ORDER BY u.id LIMIT 1"
            ),
            {"department_id": cs_department_id},
        ).first()
        if hod_user:
            bind.execute(
                sa.text(
                    "UPDATE departments SET hod_user_id = :hod_user_id "
                    "WHERE id = :department_id AND hod_user_id IS NULL"
                ),
                {"hod_user_id": hod_user[0], "department_id": cs_department_id},
            )

    inspector = sa.inspect(bind)
    for table_name in ("student_profiles", "faculty_profiles"):
        if inspector.has_table(table_name):
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.alter_column(
                    "department_id",
                    existing_type=sa.Integer(),
                    nullable=False,
                )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("faculty_profiles"):
        with op.batch_alter_table("faculty_profiles") as batch_op:
            batch_op.alter_column("department_id", existing_type=sa.Integer(), nullable=True)
    if inspector.has_table("student_profiles"):
        with op.batch_alter_table("student_profiles") as batch_op:
            batch_op.alter_column("department_id", existing_type=sa.Integer(), nullable=True)

    inspector = sa.inspect(bind)
    if inspector.has_table("departments") and "hod_user_id" in {
        column["name"] for column in inspector.get_columns("departments")
    }:
        if any(
            index["name"] == "uq_departments_hod_user_id"
            for index in inspector.get_indexes("departments")
        ):
            op.drop_index("uq_departments_hod_user_id", table_name="departments")
        with op.batch_alter_table("departments") as batch_op:
            batch_op.drop_column("hod_user_id")
