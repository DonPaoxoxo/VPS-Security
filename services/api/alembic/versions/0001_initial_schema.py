"""Initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-02

This baseline migration creates every table directly from the current
ssc_core SQLAlchemy metadata rather than hand-transcribing 26 `op.create_table`
calls, so the generated DDL (enums, UUID/JSONB columns, foreign keys) can
never drift from the ORM models it was generated against. Once this baseline
is applied to a real database, generate all subsequent migrations the normal
way with `alembic revision --autogenerate` so future diffs stay incremental.
"""

from typing import Sequence, Union

from alembic import op

from ssc_core.db import Base
from ssc_core.models import *  # noqa: F401,F403 — registers all tables on Base.metadata

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
