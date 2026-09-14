"""Durable processing state and document categories."""
import sqlalchemy as sa

from alembic import op

revision = "e05b2f74d936"
down_revision = "d94a1e63c825"
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("processing_progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_error", sa.String(255), nullable=True),
        sa.Column("processing_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_token", sa.String(36), nullable=True),
    ):
        op.add_column("documents", column)


def downgrade():
    for name in ("processing_token", "processing_available_at", "processing_error", "processing_attempts", "processing_progress", "processing_status", "category"):
        op.drop_column("documents", name)
