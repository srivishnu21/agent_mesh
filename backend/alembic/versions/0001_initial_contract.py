"""initial contract schema

Revision ID: 0001_initial_contract
Revises:
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_contract"
down_revision = None
branch_labels = None
depends_on = None


run_status = postgresql.ENUM("pending", "running", "completed", "failed", name="runstatus")
run_event_type = postgresql.ENUM(
    "run_started",
    "run_completed",
    "node_started",
    "node_completed",
    "agent_message",
    "tool_call",
    "tool_result",
    "llm_call",
    "error",
    name="runeventtype",
)
channel = postgresql.ENUM("telegram", "slack", "web", name="channel")
message_role = postgresql.ENUM("user", "agent", "system", name="messagerole")


def upgrade() -> None:
    bind = op.get_bind()
    run_status.create(bind, checkfirst=True)
    run_event_type.create(bind, checkfirst=True)
    channel.create(bind, checkfirst=True)
    message_role.create(bind, checkfirst=True)

    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True, index=True),
        sa.Column("role", sa.String(length=240), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("tools", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("channels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agents_name", "agents", ["name"])

    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("graph", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_template", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workflow_id", sa.Uuid(), sa.ForeignKey("workflows.id"), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("trigger", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
    )

    op.create_table(
        "run_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("event_type", run_event_type, nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("channel", channel, nullable=False),
        sa.Column("external_id", sa.String(length=240), nullable=False, index=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversations_external_id", "conversations", ["external_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_index("ix_conversations_external_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_table("run_events")
    op.drop_table("runs")
    op.drop_table("workflows")
    op.drop_index("ix_agents_name", table_name="agents")
    op.drop_table("agents")
    message_role.drop(op.get_bind(), checkfirst=True)
    channel.drop(op.get_bind(), checkfirst=True)
    run_event_type.drop(op.get_bind(), checkfirst=True)
    run_status.drop(op.get_bind(), checkfirst=True)
