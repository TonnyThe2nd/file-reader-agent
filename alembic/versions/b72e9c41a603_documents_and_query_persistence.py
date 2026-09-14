import sqlalchemy as sa

from alembic import op

revision = "b72e9c41a603"
down_revision = "ace48b94f7c9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("owner_id", "sha256", "mime_type", name="uq_document_owner_hash_mime"),
    )
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "document_id", "embedding_model", "position", name="uq_chunk_model_position"
        ),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    with op.batch_alter_table("interactions") as batch:
        batch.add_column(
            sa.Column("owner_id", sa.String(100), nullable=False, server_default="local")
        )
        batch.add_column(sa.Column("document_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("cache_key", sa.String(64), nullable=True))
        batch.add_column(sa.Column("mode", sa.String(10), nullable=False, server_default="direct"))
        batch.add_column(
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0")
        )
        batch.create_foreign_key(
            "fk_interactions_document_id", "documents", ["document_id"], ["id"], ondelete="SET NULL"
        )
        for column in ("owner_id", "document_id", "cache_key"):
            batch.create_index(f"ix_interactions_{column}", [column])


def downgrade():
    with op.batch_alter_table("interactions") as batch:
        batch.drop_constraint("fk_interactions_document_id", type_="foreignkey")
        for column in ("owner_id", "document_id", "cache_key"):
            batch.drop_index(f"ix_interactions_{column}")
        for column in (
            "output_tokens",
            "input_tokens",
            "mode",
            "cache_key",
            "document_id",
            "owner_id",
        ):
            batch.drop_column(column)
    op.drop_table("document_chunks")
    op.drop_table("documents")
