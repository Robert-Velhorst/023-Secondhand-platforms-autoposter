"""Add worker heartbeat records for operational readiness.

Revision ID: 20260715_0011
Revises: 20260703_0010
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0011"
down_revision: str | None = "20260703_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "worker_heartbeats" in inspector.get_table_names():
        return
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("worker_id"),
    )
    op.create_index("ix_worker_heartbeats_last_seen_at", "worker_heartbeats", ["last_seen_at"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "worker_heartbeats" in inspector.get_table_names():
        op.drop_index("ix_worker_heartbeats_last_seen_at", table_name="worker_heartbeats")
        op.drop_table("worker_heartbeats")
