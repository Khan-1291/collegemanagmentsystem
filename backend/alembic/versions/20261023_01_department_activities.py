"""Add department activity posts.

Revision ID: 20261023_01
Revises: 20261016_01
Create Date: 2026-10-23
"""

from alembic import op
import sqlalchemy as sa


revision = "20261023_01"
down_revision = "20261016_01"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if sa.inspect(bind).has_table("activity_posts"):
        return

    op.create_table(
        "activity_posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("attachment_storage_key", sa.String(length=255), nullable=True),
        sa.Column("attachment_filename", sa.String(length=255), nullable=True),
        sa.Column("attachment_content_type", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activity_posts_author_id", "activity_posts", ["author_id"])
    op.create_index("ix_activity_posts_category", "activity_posts", ["category"])
    op.create_index("ix_activity_posts_created_at", "activity_posts", ["created_at"])


def downgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("activity_posts"):
        return
    op.drop_index("ix_activity_posts_created_at", table_name="activity_posts")
    op.drop_index("ix_activity_posts_category", table_name="activity_posts")
    op.drop_index("ix_activity_posts_author_id", table_name="activity_posts")
    op.drop_table("activity_posts")
