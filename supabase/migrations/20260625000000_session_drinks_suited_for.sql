ALTER TABLE session_drinks
  ADD COLUMN IF NOT EXISTS suited_for jsonb NOT NULL DEFAULT '[]';
