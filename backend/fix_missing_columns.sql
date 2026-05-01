-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- Adds columns that are defined in the SQLAlchemy models but were never
-- applied to the live database (no Alembic migrations exist for this project).

-- user_profiles: GDPR consent fields (needed by /api/v1/account/consent and /export)
ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS consent_given     BOOLEAN     NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS consent_given_at  TIMESTAMPTZ          DEFAULT NULL;

-- user_profiles: email column (used by account export and distress agent)
ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS email VARCHAR UNIQUE DEFAULT NULL;

-- Verify the result
SELECT column_name, data_type, is_nullable, column_default
FROM   information_schema.columns
WHERE  table_name = 'user_profiles'
ORDER  BY ordinal_position;
