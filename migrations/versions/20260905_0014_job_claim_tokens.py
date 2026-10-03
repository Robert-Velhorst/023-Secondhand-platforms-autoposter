"""Fence publishing execution with an explicit claim identifier.

Revision ID: 20260905_0014
Revises: 20260809_0013
"""

import sqlalchemy as sa
from alembic import op

revision = "20260905_0014"
down_revision = "20260809_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("publishing_jobs")}
    if "claim_token" not in columns:
        op.add_column("publishing_jobs", sa.Column("claim_token", sa.String(32), nullable=True))


def downgrade() -> None:
    # Native DROP COLUMN (SQLite >= 3.35) avoids rebuilding/dropping the parent
    # table, which can cascade-delete its logs and attempts with foreign keys on.
    op.drop_column("publishing_jobs", "claim_token")
