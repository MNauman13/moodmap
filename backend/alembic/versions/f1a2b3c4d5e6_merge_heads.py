"""merge heads: moodscore pk + love/optimism columns

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0, d4e5f6a7b8c9
Create Date: 2026-05-03 00:00:00.000000

Merges two independent branches that both descend from c3d4e5f6a7b8:
  - e5f6a7b8c9d0: replace mood_scores PK with (entry_id, user_id, time)
  - d4e5f6a7b8c9: add text_love and text_optimism columns to mood_scores
"""

from typing import Sequence, Union

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = ("e5f6a7b8c9d0", "d4e5f6a7b8c9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
