"""add workflow_id to conversations

Revision ID: 0004_conversation_workflow
Revises: 0003_memory_and_guardrails
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_conversation_workflow"
down_revision = "0003_memory_and_guardrails"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("workflow_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_workflow_id",
        "conversations",
        "workflows",
        ["workflow_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_conversations_workflow_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "workflow_id")
