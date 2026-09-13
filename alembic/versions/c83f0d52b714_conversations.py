from alembic import op
import sqlalchemy as sa

revision = "c83f0d52b714"
down_revision = "b72e9c41a603"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.String(100), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_conversations_owner_id", "conversations", ["owner_id"])
    with op.batch_alter_table("interactions") as batch:
        batch.add_column(sa.Column("conversation_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("turn_number", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_interactions_conversation",
            "conversations",
            ["conversation_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_interactions_conversation_id", ["conversation_id"])


def downgrade():
    with op.batch_alter_table("interactions") as batch:
        batch.drop_index("ix_interactions_conversation_id")
        batch.drop_constraint("fk_interactions_conversation", type_="foreignkey")
        batch.drop_column("turn_number")
        batch.drop_column("conversation_id")
    op.drop_table("conversations")
