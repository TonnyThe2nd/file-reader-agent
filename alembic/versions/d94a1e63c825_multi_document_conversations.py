import sqlalchemy as sa

from alembic import op

revision = "d94a1e63c825"
down_revision = "c83f0d52b714"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversations", sa.Column("document_ids", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("conversations", "document_ids")
