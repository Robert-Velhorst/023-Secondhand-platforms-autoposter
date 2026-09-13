"""Add persistent operator emergency controls.

Revision ID: 20260808_0012
Revises: 20260715_0011
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0012"
down_revision: str | None = "20260715_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "operator_controls" in inspector.get_table_names():
        return
    op.create_table(
        "operator_controls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "job_processing_paused",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("reason", sa.String(length=500), nullable=False, server_default=""),
        sa.Column(
            "updated_by",
            sa.String(length=120),
            nullable=False,
            server_default="operator-cli",
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "operator_controls" in inspector.get_table_names():
        op.drop_table("operator_controls")
