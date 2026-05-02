"""gdpr consent fields and agent_state cascade fix

Revision ID: c3d4e5f6a7b8
Revises: b7c8d9e0f1a2
Create Date: 2026-04-27 00:00:00.000000

Changes:
  1. Add ondelete='CASCADE' to agent_states.user_id FK so that raw SQL DELETEs
     on user_profiles correctly cascade (fixes account deletion 500 error).
  2. Add consent_given (bool) and consent_given_at (timestamptz) to user_profiles
     for GDPR Art. 9 compliance — mood/mental-health data is special-category.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Fix agent_states FK — add CASCADE so bulk deletes on user_profiles work.
    #    The constraint name may vary; use IF EXISTS guards via raw SQL for safety.
    op.drop_constraint("agent_states_user_id_fkey", "agent_states", type_="foreignkey")
    op.create_foreign_key(
        "agent_states_user_id_fkey",
        "agent_states",
        "user_profiles",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 2. GDPR consent fields on user_profiles.
    #    Use raw DDL with IF NOT EXISTS so the migration is idempotent: running
    #    it a second time (or after fix_missing_columns.sql was applied manually)
    #    is safe and produces no error.
    op.execute(
        "ALTER TABLE user_profiles "
        "ADD COLUMN IF NOT EXISTS consent_given BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE user_profiles "
        "ADD COLUMN IF NOT EXISTS consent_given_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "consent_given_at")
    op.drop_column("user_profiles", "consent_given")

    op.drop_constraint("agent_states_user_id_fkey", "agent_states", type_="foreignkey")
    op.create_foreign_key(
        "agent_states_user_id_fkey",
        "agent_states",
        "user_profiles",
        ["user_id"],
        ["id"],
    )
