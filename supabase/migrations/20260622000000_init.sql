-- Migration 001 — initial schema
-- Apply in Supabase SQL editor (Dashboard → SQL Editor → New query).
-- Safe to run multiple times: all DDL uses IF NOT EXISTS / OR REPLACE.

-- ============================================================
-- TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS bottles (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  name        text not null,
  category    text not null,
  subcategory text,
  is_active   boolean not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS companions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  name       text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  UNIQUE(user_id, name)
);

-- Preferences are append-only (no updates). UNIQUE(companion_id, value)
-- means a value can only be liked OR disliked, never both.
CREATE TABLE IF NOT EXISTS companion_preferences (
  id           uuid primary key default gen_random_uuid(),
  companion_id uuid not null references companions(id) on delete cascade,
  type         text not null check (type in ('like', 'dislike')),
  value        text not null,
  created_at   timestamptz not null default now(),
  UNIQUE(companion_id, value)
);

CREATE TABLE IF NOT EXISTS sessions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  occasion   text not null,
  mood       text,
  created_at timestamptz not null default now(),
  ended_at   timestamptz
);

-- Enforce at most one open session per user.
CREATE UNIQUE INDEX IF NOT EXISTS one_open_session_per_user
  ON sessions(user_id)
  WHERE ended_at IS NULL;

CREATE TABLE IF NOT EXISTS session_companions (
  session_id   uuid not null references sessions(id) on delete cascade,
  companion_id uuid not null references companions(id) on delete cascade,
  primary key (session_id, companion_id)
);

-- ingredient source values: "inventory" | "pantry" | "perishable" | "missing"
CREATE TABLE IF NOT EXISTS session_drinks (
  id          uuid primary key default gen_random_uuid(),
  session_id  uuid not null references sessions(id) on delete cascade,
  name        text not null,
  ingredients jsonb not null,
  steps       jsonb not null default '[]',
  why         text not null default '',
  verdict     text check (verdict in ('liked', 'disliked', 'neutral')),
  created_at  timestamptz not null default now()
);

-- ============================================================
-- UPDATED_AT TRIGGER (bottles + companions only)
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS bottles_updated_at ON bottles;
CREATE TRIGGER bottles_updated_at
  BEFORE UPDATE ON bottles
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS companions_updated_at ON companions;
CREATE TRIGGER companions_updated_at
  BEFORE UPDATE ON companions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE bottles               ENABLE ROW LEVEL SECURITY;
ALTER TABLE companions            ENABLE ROW LEVEL SECURITY;
ALTER TABLE companion_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions              ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_companions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_drinks        ENABLE ROW LEVEL SECURITY;

-- Drop and recreate policies so this script is idempotent.
DROP POLICY IF EXISTS "own bottles"            ON bottles;
DROP POLICY IF EXISTS "own companions"         ON companions;
DROP POLICY IF EXISTS "own preferences"        ON companion_preferences;
DROP POLICY IF EXISTS "own sessions"           ON sessions;
DROP POLICY IF EXISTS "own session_companions" ON session_companions;
DROP POLICY IF EXISTS "own session_drinks"     ON session_drinks;

CREATE POLICY "own bottles" ON bottles
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "own companions" ON companions
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "own preferences" ON companion_preferences
  FOR ALL USING (
    companion_id IN (SELECT id FROM companions WHERE user_id = auth.uid())
  );

CREATE POLICY "own sessions" ON sessions
  FOR ALL USING (auth.uid() = user_id);

-- session_companions: gate on session ownership. Application layer
-- must also validate that companion_id belongs to the same user
-- before inserting (RLS alone cannot enforce cross-table user match here).
CREATE POLICY "own session_companions" ON session_companions
  FOR ALL USING (
    session_id IN (SELECT id FROM sessions WHERE user_id = auth.uid())
  );

CREATE POLICY "own session_drinks" ON session_drinks
  FOR ALL USING (
    session_id IN (SELECT id FROM sessions WHERE user_id = auth.uid())
  );

-- ============================================================
-- RPCS FOR ATOMIC PREFERENCE UPSERT
-- supabase-py REST cannot do DELETE+INSERT atomically; these
-- functions run inside a single Postgres transaction.
-- SECURITY DEFINER so they can bypass RLS on companion_preferences
-- (the calling endpoint validates companion ownership first).
-- ============================================================

CREATE OR REPLACE FUNCTION upsert_companion_like(
  p_companion_id uuid,
  p_value        text
) RETURNS void LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO companion_preferences(companion_id, type, value)
  VALUES (p_companion_id, 'like', p_value)
  ON CONFLICT (companion_id, value) DO UPDATE SET type = 'like';
END;
$$;

CREATE OR REPLACE FUNCTION upsert_companion_dislike(
  p_companion_id uuid,
  p_value        text
) RETURNS void LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO companion_preferences(companion_id, type, value)
  VALUES (p_companion_id, 'dislike', p_value)
  ON CONFLICT (companion_id, value) DO UPDATE SET type = 'dislike';
END;
$$;
