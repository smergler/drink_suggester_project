# ADR-001: How user data is isolated (RLS, not app-enforced filtering)

**Status:** Accepted · **Date:** 2026-06-22 · **Scope:** the future multi-user backend
(NOT the Task 3 thin-slice demo, which has no DB and a hardcoded inventory).

## Context

The app is multi-tenant: each user owns their inventory, companions, and session
history. An earlier draft spec called for Supabase Auth (JWT) + a Supabase Postgres DB
with **Row Level Security (RLS) policies** restricting every table to
`auth.uid() = user_id` — while *also* specifying database access via **raw asyncpg**.

## Problem

Those two choices are incompatible, and the failure is silent.

RLS keys off `auth.uid()`, which Postgres derives from the JWT passed through the
Supabase API (PostgREST). A raw **asyncpg** connection talks straight to Postgres as
the connection-string role — effectively the service/owner role — with **no JWT and
no `auth.uid()`**. Owner/service roles **bypass RLS entirely**.

So if we use asyncpg, every RLS policy becomes **dead code**. The only
thing protecting user A's data from user B is the application remembering to add
`WHERE user_id = $1` to every single query, forever. One forgotten filter on one
endpoint = a full cross-user data leak, with no second line of defense. It's a vault
door with the wall knocked out beside it.

## Options

1. **asyncpg + app-enforced `WHERE user_id`.** Fast, but RLS is theater — delete it
   so it doesn't give false confidence. Single point of failure: every query, forever.
2. **Supabase client (PostgREST) with the user's JWT.** RLS actually fires. Defense in
   depth (app *and* DB must both fail to leak). Slightly slower; simpler auth.
3. **asyncpg + `SET LOCAL request.jwt.claims` / role per request** so RLS fires over the
   direct connection. Best of both, but fiddly — get the per-connection claim injection
   subtly wrong and you silently fall back to leaking.

## Decision

**Option 2: Supabase client + user JWT, with RLS as the enforcement boundary.**

Rationale for this project:
- **Defense in depth.** Postgres enforces isolation even if app code has a bug; the app
  must *and* the DB must both fail before data leaks.
- **Performance is irrelevant here.** This is a personal/portfolio-scale app; asyncpg's
  throughput edge buys nothing measurable and would cost the only real safety guarantee.
- **It makes the P6 RLS policies real** instead of decorative — no rewrite of the schema work.
- **Fewer moving parts** than Option 3, and defensible in an interview in one sentence.

## Consequences / guardrails

- **Do NOT use raw `asyncpg` (or any service-role direct connection) for user-scoped
  reads/writes.** That bypasses RLS. This is the one rule that must not regress.
- Access user data through the Supabase client carrying the end user's JWT so
  `auth.uid()` is populated and policies apply.
- Keep RLS policies on every user-owned table (`auth.uid() = user_id`); treat them as
  the security boundary, not as belt-and-suspenders.
- If throughput ever genuinely matters, revisit **Option 3** (deliberately, with tests
  that prove RLS still fires over the direct connection) — never silently drop to Option 1.

## Interview one-liner

"I chose DB-enforced row-level security over app-enforced `WHERE user_id` filtering,
because in a multi-tenant app a single forgotten filter is a data breach — and I caught
that wiring up raw asyncpg would have silently bypassed RLS and made the policies dead code."
