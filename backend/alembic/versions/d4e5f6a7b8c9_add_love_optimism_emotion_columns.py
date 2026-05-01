"""add text_love and text_optimism emotion columns to mood_scores

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-30 00:00:00.000000

Changes:
  Expand emotion model from 7 to 9 categories by adding text_love and
  text_optimism columns. Existing rows get NULL for the new columns.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('mood_scores', sa.Column('text_love', sa.Float(), nullable=True))
    op.add_column('mood_scores', sa.Column('text_optimism', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('mood_scores', 'text_optimism')
    op.drop_column('mood_scores', 'text_love')
