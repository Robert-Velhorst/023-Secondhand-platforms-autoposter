"""Persist OAuth token-file cleanup requests across process failures.

Revision ID: 20261001_0017
Revises: 20260913_0016
"""

import sqlalchemy as sa
from alembic import op

revision = "20261001_0017"
down_revision = "20260913_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("token_secret_deletions"):
        required = {
            "id", "secret_ref", "created_at", "next_attempt_at", "attempts", "claim_token", "last_error_type"
        }
        columns = {column["name"] for column in inspector.get_columns("token_secret_deletions")}
        if not required.issubset(columns):
            raise RuntimeError("Existing token_secret_deletions schema does not match the cleanup outbox")
        if "ix_token_secret_deletions_due" not in {
            index["name"] for index in inspector.get_indexes("token_secret_deletions")
        }:
            op.create_index(
                "ix_token_secret_deletions_due", "token_secret_deletions", ["next_attempt_at", "id"]
            )
        return
    op.create_table(
        "token_secret_deletions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("secret_ref", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("claim_token", sa.String(32), nullable=True),
        sa.Column("last_error_type", sa.String(80), nullable=False),
    )
    op.create_index("ix_token_secret_deletions_due", "token_secret_deletions", ["next_attempt_at", "id"])


def downgrade() -> None:
    pending = op.get_bind().execute(sa.text("SELECT count(*) FROM token_secret_deletions")).scalar_one()
    if pending:
        raise RuntimeError("Drain token_secret_deletions before downgrading this migration")
    op.drop_index("ix_token_secret_deletions_due", table_name="token_secret_deletions")
    op.drop_table("token_secret_deletions")
