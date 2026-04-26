"""add performance indexes for hot query columns

Revision ID: a1b2c3d4e5f6
Revises: 79054a8d065c
Create Date: 2026-04-25 12:00:00.000000

Adds composite indexes on the three tables hit by every dashboard load:
- mood_scores(user_id, time DESC)   — insights + nightly agent 7-day window
- journal_entries(user_id, created_at DESC) — journal list + daily cap check
- nudges(user_id, sent_at DESC)     — nudges list + 24h cooldown check

Before: O(n) full-table scans per user query.
After:  O(log n) index seeks; gains compound as user data grows.
"""

from typing import Sequence, Union
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "79054a8d065c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_mood_scores_user_time",
        "mood_scores",
        ["user_id", "time"],
        postgresql_ops={"time": "DESC"},
    )
    op.create_index(
        "ix_journal_entries_user_created",
        "journal_entries",
        ["user_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "ix_nudges_user_sent",
        "nudges",
        ["user_id", "sent_at"],
        postgresql_ops={"sent_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_nudges_user_sent", table_name="nudges")
    op.drop_index("ix_journal_entries_user_created", table_name="journal_entries")
    op.drop_index("ix_mood_scores_user_time", table_name="mood_scores")
