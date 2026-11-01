"""Enforce at most one owner account at the database level

Revision ID: 0002_singleton_owner_constraint
Revises: 0001_initial_schema
Create Date: 2026-11-02

The application already checks "does a user exist?" before creating the
owner account, but that check-then-insert is not atomic — two concurrent
POST /auth/setup requests could both pass the check before either commits,
creating two owner accounts. A partial unique index on a constant expression,
scoped to `WHERE is_owner`, makes a second such row impossible regardless of
timing: Postgres enforces it as part of the INSERT itself.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002_singleton_owner_constraint"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX ix_users_singleton_owner ON users ((true)) WHERE is_owner"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_singleton_owner")
