-- P10: Add telemetry columns to sessions.
-- Existing rows get NULL (telemetry is best-effort; NULL excluded from aggregates).
ALTER TABLE sessions
  ADD COLUMN IF NOT EXISTS bottle_count   integer,
  ADD COLUMN IF NOT EXISTS input_tokens   integer,
  ADD COLUMN IF NOT EXISTS output_tokens  integer,
  ADD COLUMN IF NOT EXISTS latency_ms     integer;
