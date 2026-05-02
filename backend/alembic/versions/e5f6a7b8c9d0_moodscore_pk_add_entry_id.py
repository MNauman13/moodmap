"""moodscore pk add entry_id

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-05-01 00:00:00.000000

Changes:
  Replaces the (time, user_id) composite PK on mood_scores with
  (entry_id, user_id, time).  entry_id being first in the PK guarantees
  uniqueness per analysis run and eliminates the theoretical microsecond
  collision window that existed with the old PK.

  If the table is already a TimescaleDB hypertable you must run
  `SELECT drop_chunks(...)` and `SELECT detach_data_node(...)` first, or
  recreate it — this migration is written for a plain PostgreSQL table.
  If you are on TimescaleDB, run the raw SQL manually after consulting the
  TimescaleDB docs for hypertable PK changes.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old (time, user_id) primary key and replace with (entry_id, user_id, time).
    # We use raw SQL so the exact constraint name is irrelevant.
    op.execute("ALTER TABLE mood_scores DROP CONSTRAINT IF EXISTS mood_scores_pkey")

    # Ensure entry_id is NOT NULL before promoting it to PK.
    # Existing rows that somehow have a NULL entry_id would block this; delete them.
    op.execute("DELETE FROM mood_scores WHERE entry_id IS NULL")
    op.execute("ALTER TABLE mood_scores ALTER COLUMN entry_id SET NOT NULL")

    op.execute(
        "ALTER TABLE mood_scores "
        "ADD CONSTRAINT mood_scores_pkey "
        "PRIMARY KEY (entry_id, user_id, time)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE mood_scores DROP CONSTRAINT IF EXISTS mood_scores_pkey")
    op.execute(
        "ALTER TABLE mood_scores "
        "ADD CONSTRAINT mood_scores_pkey "
        "PRIMARY KEY (time, user_id)"
    )
    op.execute("ALTER TABLE mood_scores ALTER COLUMN entry_id DROP NOT NULL")
