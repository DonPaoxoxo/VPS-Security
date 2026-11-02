"""Widen performance_metrics network byte counters to BIGINT

Revision ID: 0003_bigint_network_bytes
Revises: 0002_singleton_owner_constraint
Create Date: 2026-11-02

Linux agents report cumulative network byte counters, which on a long-lived
interface routinely exceed PostgreSQL's signed INT4 maximum (2147483647) —
confirmed in production by asyncpg.exceptions.DataError on insert. Widening
an existing INTEGER column to BIGINT is a lossless, in-place type change for
every value already stored, so no data is deleted or rewritten; Postgres
only needs to verify the new type fits, which it always does when widening.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_bigint_network_bytes"
down_revision: Union[str, None] = "0002_singleton_owner_constraint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "performance_metrics",
        "network_rx_bytes",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
    op.alter_column(
        "performance_metrics",
        "network_tx_bytes",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Deliberately NOT implemented as a plain alter_column back to INTEGER:
    # any row already holding a value above 2147483647 — the entire reason
    # this migration exists — would either raise or, depending on driver
    # settings, silently truncate. Truncating security telemetry silently
    # is worse than refusing the downgrade outright.
    raise NotImplementedError(
        "Downgrading network_rx_bytes/network_tx_bytes to INTEGER would silently "
        "truncate or fail on any value already recorded above 2147483647. "
        "If you must revert, archive/export performance_metrics rows with "
        "network_rx_bytes or network_tx_bytes > 2147483647 first, then perform "
        "the narrowing cast manually with an explicit decision on how to handle them."
    )
