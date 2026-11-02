"""Allow more than one owner/admin account

Revision ID: 0004_multi_owner_accounts
Revises: 0003_bigint_network_bytes
Create Date: 2026-11-03

The platform was originally single-owner only, enforced at the database
level by a partial unique index (migration 0002) that made a second
`is_owner=True` row impossible. The product now supports multiple equal
administrator accounts, so that constraint is dropped. Dropping a unique
index never rejects existing data (it only removes a restriction), so this
is safe to apply regardless of how many owner rows already exist.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0004_multi_owner_accounts"
down_revision: Union[str, None] = "0003_bigint_network_bytes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_singleton_owner")


def downgrade() -> None:
    # Recreating the singleton constraint will fail with a unique-violation
    # at index-creation time if more than one owner row exists by then —
    # which is the correct behavior: silently deleting/demoting the extra
    # admin accounts to make the downgrade succeed is not this migration's
    # call to make.
    op.execute(
        "CREATE UNIQUE INDEX ix_users_singleton_owner ON users ((true)) WHERE is_owner"
    )
