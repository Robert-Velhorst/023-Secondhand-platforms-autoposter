"""Add owner-scoped HAI connector credentials and listing change cursor.

Revision ID: 20260809_0013
Revises: 20260808_0012
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0013"
down_revision: str | None = "20260808_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "hai_connector_tokens" not in tables:
        op.create_table(
            "hai_connector_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("scope", sa.String(length=80), nullable=False, server_default="hai:read"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
        op.create_index("ix_hai_connector_tokens_user_id", "hai_connector_tokens", ["user_id"])
        op.create_index(
            "ix_hai_connector_tokens_user_created_at", "hai_connector_tokens", ["user_id", "created_at"]
        )
        op.create_index("ix_hai_connector_tokens_expires_at", "hai_connector_tokens", ["expires_at"])
        op.create_index("ix_hai_connector_tokens_token_hash", "hai_connector_tokens", ["token_hash"])

    if "hai_listing_changes" not in tables:
        op.create_table(
            "hai_listing_changes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("listing_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=20), nullable=False),
            sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_hai_listing_changes_owner_id", "hai_listing_changes", ["owner_id"])
        op.create_index("ix_hai_listing_changes_listing_id", "hai_listing_changes", ["listing_id"])
        op.create_index("ix_hai_listing_changes_owner_id_id", "hai_listing_changes", ["owner_id", "id"])
        op.execute(
            sa.text(
                "INSERT INTO hai_listing_changes (owner_id, listing_id, action, changed_at) "
                "SELECT owner_id, id, 'upsert', CURRENT_TIMESTAMP FROM listings"
            )
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "hai_listing_changes" in tables:
        op.drop_table("hai_listing_changes")
    if "hai_connector_tokens" in tables:
        op.drop_table("hai_connector_tokens")
