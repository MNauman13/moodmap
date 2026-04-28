"""add user email and cascade mood score deletes

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-04-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("email", sa.String(), nullable=True))
    op.create_index(op.f("ix_user_profiles_email"), "user_profiles", ["email"], unique=True)

    op.drop_constraint("mood_scores_entry_id_fkey", "mood_scores", type_="foreignkey")
    op.create_foreign_key(
        "mood_scores_entry_id_fkey",
        "mood_scores",
        "journal_entries",
        ["entry_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("mood_scores_entry_id_fkey", "mood_scores", type_="foreignkey")
    op.create_foreign_key(
        "mood_scores_entry_id_fkey",
        "mood_scores",
        "journal_entries",
        ["entry_id"],
        ["id"],
    )

    op.drop_index(op.f("ix_user_profiles_email"), table_name="user_profiles")
    op.drop_column("user_profiles", "email")
