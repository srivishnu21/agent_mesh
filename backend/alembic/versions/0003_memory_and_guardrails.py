"""add conversation memory + new event types

Revision ID: 0003_memory_and_guardrails
Revises: 0002_add_runtime_event_types
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_memory_and_guardrails"
down_revision = "0002_add_runtime_event_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE runeventtype ADD VALUE IF NOT EXISTS 'guardrail_triggered'")
    op.execute("ALTER TYPE runeventtype ADD VALUE IF NOT EXISTS 'edge_routed'")
    op.execute("ALTER TYPE runeventtype ADD VALUE IF NOT EXISTS 'memory_updated'")

    op.create_table(
        "conversation_memories",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "agent_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("conversation_id", "agent_id", name="uq_conversation_memory"),
    )


def downgrade() -> None:
    op.drop_table("conversation_memories")
    # Enum value removal requires rebuild on Postgres; leave irreversible.
