"""Add profile images and department activity comments.

Revision ID: 20261025_01
Revises: 20261023_01
Create Date: 2026-10-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20261025_01"
down_revision = "20261023_01"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("users") and "profile_image_url" not in {
        column["name"] for column in inspector.get_columns("users")
    }:
        op.add_column("users", sa.Column("profile_image_url", sa.String(length=255), nullable=True))

    if not inspector.has_table("activity_comments"):
        op.create_table(
            "activity_comments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("activity_id", sa.Integer(), nullable=False),
            sa.Column("author_id", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["activity_id"], ["activity_posts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_activity_comments_activity_id", "activity_comments", ["activity_id"])
        op.create_index("ix_activity_comments_author_id", "activity_comments", ["author_id"])
        op.create_index("ix_activity_comments_created_at", "activity_comments", ["created_at"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("activity_comments"):
        indexes = {index["name"] for index in inspector.get_indexes("activity_comments")}
        for index_name in (
            "ix_activity_comments_created_at",
            "ix_activity_comments_author_id",
            "ix_activity_comments_activity_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="activity_comments")
        op.drop_table("activity_comments")

    if inspector.has_table("users") and "profile_image_url" in {
        column["name"] for column in inspector.get_columns("users")
    }:
        op.drop_column("users", "profile_image_url")
