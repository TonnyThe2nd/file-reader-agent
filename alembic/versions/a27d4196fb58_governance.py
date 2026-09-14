"""Policies, grants, audit trail and atomic quota counters."""
import sqlalchemy as sa

from alembic import op

revision = "a27d4196fb58"
down_revision = "f16c3085ea47"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("user_policies", sa.Column("owner_id", sa.String(100), primary_key=True), sa.Column("role", sa.String(20), nullable=False), sa.Column("teams", sa.JSON(), nullable=False), sa.Column("daily_queries", sa.Integer(), nullable=False), sa.Column("daily_tokens", sa.Integer(), nullable=False), sa.Column("storage_bytes", sa.Integer(), nullable=False), sa.Column("retention_days", sa.Integer(), nullable=True))
    op.create_table("document_grants", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False), sa.Column("kind", sa.String(10), nullable=False), sa.Column("recipient", sa.String(100), nullable=False), sa.UniqueConstraint("document_id", "kind", "recipient", name="uq_document_grant"))
    op.create_index("ix_document_grants_document_id", "document_grants", ["document_id"])
    op.create_table("audit_events", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("owner_id", sa.String(100), nullable=False), sa.Column("action", sa.String(50), nullable=False), sa.Column("resource_id", sa.String(100), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_audit_events_owner_id", "audit_events", ["owner_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_table("interaction_documents", sa.Column("interaction_id", sa.Uuid(), sa.ForeignKey("interactions.id", ondelete="CASCADE"), primary_key=True), sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True))
    op.execute("INSERT INTO interaction_documents (interaction_id, document_id) SELECT id, document_id FROM interactions WHERE document_id IS NOT NULL")
    op.create_table("daily_usage", sa.Column("owner_id", sa.String(100), primary_key=True), sa.Column("day", sa.String(10), primary_key=True), sa.Column("queries", sa.Integer(), nullable=False), sa.Column("tokens", sa.Integer(), nullable=False))


def downgrade():
    for name in ("daily_usage", "interaction_documents", "audit_events", "document_grants", "user_policies"):
        op.drop_table(name)
