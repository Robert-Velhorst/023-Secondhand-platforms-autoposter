"""Fence concurrent login completion without discarding existing throttle state.

Revision ID: 20260913_0016
Revises: 20260913_0015
"""

import sqlalchemy as sa
from alembic import op

revision = "20260913_0016"
down_revision = "20260913_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"]: column for column in sa.inspect(op.get_bind()).get_columns("login_throttles")}
    # Historical bootstrap creates current metadata; do not edit that migration.
    if "attempt_token" in columns:
        column = columns["attempt_token"]
        if not isinstance(column["type"], sa.String) or column["type"].length != 32 or not column["nullable"]:
            raise RuntimeError("Existing login attempt_token column does not match the expected schema")
        return
    op.add_column("login_throttles", sa.Column("attempt_token", sa.String(32), nullable=True))


def downgrade() -> None:
    if op.get_bind().execute(sa.text(
        "SELECT count(*) FROM login_throttles WHERE attempt_token IS NOT NULL"
    )).scalar_one():
        raise RuntimeError("Drain login reservations before downgrading this migration")
    op.drop_column("login_throttles", "attempt_token")
