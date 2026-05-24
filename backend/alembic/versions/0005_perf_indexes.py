"""add performance indexes for dashboard and run views

Revision ID: 0005_perf_indexes
Revises: 0004_conversation_workflow
Create Date: 2026-05-24
"""

from alembic import op


revision = "0005_perf_indexes"
down_revision = "0004_conversation_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_runs_workflow_id", "runs", ["workflow_id"])
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_index("ix_runs_started_at", "runs", ["started_at"])
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])
    op.create_index("ix_run_events_agent_id", "run_events", ["agent_id"])
    op.create_index("ix_run_events_created_at", "run_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_run_events_created_at", table_name="run_events")
    op.drop_index("ix_run_events_agent_id", table_name="run_events")
    op.drop_index("ix_run_events_run_id", table_name="run_events")
    op.drop_index("ix_runs_started_at", table_name="runs")
    op.drop_index("ix_runs_status", table_name="runs")
    op.drop_index("ix_runs_workflow_id", table_name="runs")
