# BarBack

[![CI](https://github.com/smergler/barback/actions/workflows/ci.yml/badge.svg)](https://github.com/smergler/barback/actions/workflows/ci.yml)

An LLM cocktail recommender **grounded in the user's actual bottle inventory**, built
eval-first: the centerpiece is a measurement harness that proves the recommendations only
use ingredients you own (or honestly flags what you'd need to buy), not just a model call.

> Built as an AI/ML portfolio piece. The interesting engineering is the discipline *around*
> the LLM — grounding metrics, adversarial evals, an LLM-as-judge — not the model call itself.

## What it does

Given an occasion, mood, optional companions, and constraints, it recommends cocktails it
can actually make from a known inventory. Every ingredient is labeled `inventory` (owned),
`pantry` (staple), `perishable` ("grab this"), or `missing` (specialty item you lack) — so
the system can be scored on whether it's honest about what you have.

## Why it's interesting (the eval-first angle)

The recommender is graded by a measurement harness, not vibes:

- **Grounding rate** (deterministic) — % of suggestions where every ingredient is owned,
  an allowed staple, or honestly flagged. Set math, not NLP.
- **Makeable rate** (deterministic) — does the drink actually use owned bottles, or is
  it a pure shopping list? (`uses_inventory` = ≥1 owned bottle anchors the drink;
  `makeable_now` = uses_inventory AND zero `missing` ingredients.)
- **LLM-as-judge** — the subjective dimensions (constraint adherence, occasion fit,
  recipe plausibility, name accuracy) deterministic checks can't see.

### Metrics timeline

| Milestone | Grounding | Makeable | Makeable-now | Notes |
|---|---|---|---|---|
| Mock baseline, original 8 scenarios (seeded violations) | 64% | — | — | Proved the scorer catches violations before spending a token. |
| Live baseline after prompt tightening | 100% | — | — | Grounding failure → pantry boundary fix → metric moved. |
| Mock baseline, current 12 scenarios (+ adversarial) | 53% | 88% | 50% | Lower grounding% expected: adversarial scenarios are designed to catch violations. |
| **Live run** (claude-haiku-4-5, all 12 scenarios) | **100%** | **94%** | **75%** | JUDGE: constraints 74%, occasion fit 4.6/5, plausibility 4.4/5, name accuracy 58% — model grounds perfectly but misnames ~42% of drinks. |

_See [`RESUME_STORY.md`](RESUME_STORY.md) for the full story including why 53% grounding mock ≠ regression._

See [`docs/eval-spec.md`](docs/eval-spec.md) for exact definitions and
[`RESUME_STORY.md`](RESUME_STORY.md) for the full narrative and engineering decisions.

## Security decision: DB-enforced RLS, not app-enforced `WHERE user_id`

For the future multi-user backend (see [`docs/adr-001-data-isolation.md`](docs/adr-001-data-isolation.md)):

The initial spec combined Supabase Auth (JWT + RLS policies) with raw `asyncpg` for
database access. Those two choices are **silently incompatible**: `asyncpg` connects
directly to Postgres as the service role with no JWT, so `auth.uid()` is never set and
**RLS is bypassed entirely**. Every policy becomes dead code; a single forgotten
`WHERE user_id` in application code is a cross-user data leak with no second line of defense.

Decision: **Supabase client (PostgREST) carrying the user's JWT**, so RLS actually fires.
Defense in depth: both the application *and* the database must fail before data leaks.
The throughput cost of PostgREST over a direct connection is irrelevant at personal/portfolio scale.

> **Interview one-liner:** "I chose DB-enforced row-level security over app-enforced
> `WHERE user_id` filtering, because in a multi-tenant app a single forgotten filter is
> a data breach — and I caught that wiring up raw asyncpg would have silently bypassed
> RLS and made the policies dead code."

## Architecture

```
Browser ─▶ FastAPI (/recommend, /inventory, /companions, /sessions, /session-drinks)
                │                   │
                │         Supabase Auth (JWT verification, offline)
                │                   │
                ▼                   ▼
        recommender/         backend/db.py (supabase-py + user JWT → RLS enforced)
        (framework-agnostic)         │
                │                   ▼
                │              Postgres (Supabase) — bottles, companions, sessions, drinks
                ▼
        Claude (structured output) → grounding scorer + LLM judge
```

The recommender core (`recommender/`) is framework-agnostic — no web/DB dependencies — so
it can be evaluated in isolation. The persistence layer carries the user's JWT into every
Supabase query so Postgres RLS fires, enforcing row-level isolation at the database level.

## Layout

```
recommender/       core: schemas, pantry rules, bottle matcher, LLM client, context, orchestrator
evals/             fixtures, mock responses, grounding scorer, LLM judge, runner, inspect tool
tests/             pytest unit tests — scorers, matcher, parser, judge, all API endpoints, RLS
backend/
  auth.py          JWT verification (offline, HS256, checks aud + role)
  db.py            thin CRUD wrappers — all 6 tables, 2 RPCs, one new client per request
  routers/         inventory, companions, sessions, session_drinks
app/
  main.py          FastAPI app: all routers, /recommend → real inventory + session lifecycle
  static/          vanilla JS SPA with login, inventory, companions, recommend + verdict tabs
docs/              eval-spec.md, adr-001-data-isolation.md, backend-spec.md
backend/migrations/  001_init.sql — all tables, RLS policies, triggers, RPCs (idempotent)
PLAN.md            build plan (atomic, status-tracked subtasks)
RESUME_STORY.md    narrative, metrics timeline, key decisions
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

For live calls, create `.env` at the project root (see `env.template`):

```
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_PROJECT_URL=https://...supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_JWT_TOKEN=...    # project JWT secret (Settings → API)
```

## Run

```bash
.venv/bin/python -m pytest -q                       # 105 unit tests (3 live RLS tests skipped without credentials)
.venv/bin/python -m evals.run_evals                 # offline eval (mock responses, no tokens)
.venv/bin/python -m evals.run_evals --live          # eval against the real model
.venv/bin/python -m evals.run_evals --live --judge  # + LLM judge
.venv/bin/python -m evals.inspect <scenario_id>...  # print actual suggestions for a scenario
```

## Cost

Runs on **Claude Haiku 4.5** ($1.00 / 1M input tokens, $5.00 / 1M output tokens).

Per recommendation request: ~600 input tokens (system prompt + ~20-bottle inventory +
request) and ~800 output tokens (3 structured drinks) → **≈ $0.0046**, under half a cent.

| Personal usage | Requests/mo | Est. cost/mo |
|---|---|---|
| Light (3/day) | ~90 | ~$0.40 |
| Moderate (8/day) | ~240 | ~$1.10 |
| Heavy (15/day) | ~450 | ~$2.10 |

A full offline eval run is **free** (mock responses). A full `--live --judge` run is
~30 calls ≈ **under $0.20**. Swapping to Opus 4.8 ($5/$25 per 1M) is ~5× across the board —
heavy personal use still ~$10/mo.

**Takeaway:** at personal scale the API cost is a rounding error, so the project optimizes
for *recommendation quality* (grounding / makeable / judge scores), not token cost. Cost
would only become a design factor at thousands-of-users scale.

## Run the app

```bash
.venv/bin/uvicorn app.main:app --reload
# then open http://localhost:8000
```

## Status

**All Phase 6 (persistence) tasks complete:**
- Supabase Auth (offline JWT verification, aud + role checks, service_role bypass guard)
- Full CRUD for all 6 tables via supabase-py carrying the user JWT (RLS fires on every query)
- Sessions + session_drinks with verdict → companion preference feedback (atomic via Postgres RPC)
- Multi-tab SPA frontend: login, inventory, companions, recommend + verdict buttons
- 105 passing unit tests (3 live RLS isolation tests require test credentials)
- CI gate: pytest + offline eval `--strict` on every push; Railway redeploys on push to main via GitHub integration

**Live demo:** https://barback-production.up.railway.app
