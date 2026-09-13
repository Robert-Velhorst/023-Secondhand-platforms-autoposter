"""Persist post-commit image cleanup independently of deleted accounts.

Revision ID: 20260913_0015
Revises: 20260905_0014
"""

import sqlalchemy as sa
from alembic import op

revision = "20260913_0015"
down_revision = "20260905_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historical bootstrap migration 0001 creates current model metadata. Keep
    # that published migration immutable and accept its already-created table.
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("storage_deletions"):
        required = {"id", "storage_path", "created_at", "next_attempt_at", "attempts", "claim_token", "last_error_type"}
        if not required.issubset({column["name"] for column in inspector.get_columns("storage_deletions")}):
            raise RuntimeError("Existing storage_deletions schema does not match the cleanup outbox")
        if "ix_storage_deletions_due" not in {index["name"] for index in inspector.get_indexes("storage_deletions")}:
            op.create_index("ix_storage_deletions_due", "storage_deletions", ["next_attempt_at", "id"])
        return
    op.create_table(
        "storage_deletions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("claim_token", sa.String(32), nullable=True),
        sa.Column("last_error_type", sa.String(80), nullable=False),
    )
    op.create_index("ix_storage_deletions_due", "storage_deletions", ["next_attempt_at", "id"])


def downgrade() -> None:
    # Refuse to lose pending erasure work, including temporarily leased records.
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM storage_deletions")).scalar_one()
    if count:
        raise RuntimeError("Drain storage_deletions before downgrading this migration")
    op.drop_index("ix_storage_deletions_due", table_name="storage_deletions")
    op.drop_table("storage_deletions")
