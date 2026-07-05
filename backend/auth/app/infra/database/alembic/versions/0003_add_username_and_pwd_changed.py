"""add username and token_version to users

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    # Add username in three steps so an existing (non-empty) table survives the
    # NOT NULL + UNIQUE constraint: add nullable, backfill a unique placeholder
    # from the id, then enforce.
    op.add_column("users", sa.Column("username", sa.String(length=32), nullable=True))
    op.execute(
        "UPDATE users "
        "SET username = 'user_' || left(replace(id::text, '-', ''), 8) "
        "WHERE username IS NULL"
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.alter_column("users", "username", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
    op.drop_column("users", "token_version")
