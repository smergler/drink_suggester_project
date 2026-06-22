# Drink Suggester

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

## Architecture (current)

```
RecommendRequest ─▶ pre-filter / context build ─▶ Claude (structured output)
                                                        │
                                                        ▼
                                         parse + validate (Pydantic)
                                                        │
                          ┌─────────────────────────────┼───────────────────────┐
                          ▼                             ▼                         ▼
                  grounding scorer            makeable scorer (planned)      LLM judge
                  (deterministic)              (deterministic)              (subjective)
```

The recommender core (`recommender/`) is framework-agnostic — no web/DB dependencies — so
it can be developed and evaluated in isolation, then lifted into a backend later.

## Layout

```
recommender/   core: schemas, pantry rules, bottle matcher, LLM client, context, orchestrator
evals/         fixtures, mock responses, grounding scorer, LLM judge, runner, inspect tool
tests/         pytest unit tests (scorers, matcher, parser, judge)
docs/          eval-spec.md, adr-001-data-isolation.md
PLAN.md        build plan (atomic, status-tracked subtasks) for current + future work
RESUME_STORY.md  narrative, metrics timeline, key decisions
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install pytest          # for the test suite
```

For live model calls, create a `.env` at the project root (see `env.template`):

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Run

```bash
.venv/bin/python -m pytest -q                       # unit tests
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

Recommender core, grounding eval, makeable-rate metric, and LLM judge are implemented
and tested. A FastAPI + single-page frontend slice is complete and ready to deploy.
Next up: live eval run (needs `ANTHROPIC_API_KEY`), then Railway deploy.

_A live demo link will go here once deployed._
