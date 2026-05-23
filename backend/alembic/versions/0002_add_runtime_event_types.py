"""add runtime run event types

Revision ID: 0002_add_runtime_event_types
Revises: 0001_initial_contract
Create Date: 2026-05-23
"""

from alembic import op

revision = "0002_add_runtime_event_types"
down_revision = "0001_initial_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE runeventtype ADD VALUE IF NOT EXISTS 'run_started'")
    op.execute("ALTER TYPE runeventtype ADD VALUE IF NOT EXISTS 'run_completed'")


def downgrade() -> None:
    # PostgreSQL cannot remove enum values without rebuilding the type; keep this migration irreversible.
    pass
