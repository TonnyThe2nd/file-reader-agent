"""Conversation branches reference a fixed parent prefix."""
import sqlalchemy as sa

from alembic import op

revision = "f16c3085ea47"
down_revision = "e05b2f74d936"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("parent_conversation_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("parent_turn", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_conversation_parent", "conversations", ["parent_conversation_id"], ["id"], ondelete="SET NULL")


def downgrade():
    with op.batch_alter_table("conversations") as batch:
        batch.drop_constraint("fk_conversation_parent", type_="foreignkey")
        batch.drop_column("parent_turn")
        batch.drop_column("parent_conversation_id")
