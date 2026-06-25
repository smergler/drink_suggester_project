# Eval Spec

How recommendation quality is measured. The eval is the centerpiece of the project:
the goal is not "an LLM that suggests drinks" but "an LLM whose output I can measure
and engineer." Definitions here are the source of truth; code references this doc.

## Philosophy

- **Verify mechanically what you can; judge only what you must.** Split into a
  deterministic layer (cheap, fast, unarguable) and an LLM-as-judge layer (subjective).
- **Property-based, not golden-output.** Scenarios assert *properties* of the output
  (grounded, makeable, count, constraints respected) — never exact text, which is
  non-deterministic for an LLM.
- **Mock-then-live.** Every scenario has a canned mock response (with deliberately seeded
  violations) so the full pipeline + scorers run offline at zero token cost; the same
  scenarios then run against the live model.

## The ingredient `source` model

Every ingredient in a suggestion is labeled with one of four sources (`recommender/schemas.py`,
`IngredientSource`). This turns grounding from fuzzy NLP into deterministic set math:

| source | meaning | policed? |
|---|---|---|
| `inventory` | a bottle the user owns | **yes** — must match an owned bottle |
| `pantry` | an always-stocked staple (closed set, below) | **yes** — must be in the allowlist |
| `perishable` | a non-bottle item that varies (citrus, egg, herbs, honey, spices) | no — surfaced on a "grab these" list |
| `missing` | a specialty item the user doesn't own | no — honest disclosure, surfaced |

**Pantry allowlist (closed set, `recommender/pantry.py`):** ice, water, sugar, simple
syrup, demerara syrup, rich simple syrup, salt. Temperature descriptors are normalized
("hot water" → "water"). Anything else non-alcoholic (honey, juices, spices, dairy) must
be `perishable`, not `pantry`.

## Metric 1 — Grounding rate  *(implemented)*

The primary deterministic metric (`evals/grounding.py`).

- An ingredient is **ungrounded** if it claims `source: inventory` but matches no owned
  bottle (hallucinated ownership), or claims `source: pantry` but isn't an allowlisted
  staple (assuming an item the user may not have).
- A **suggestion is grounded** iff it has zero ungrounded ingredients (per-suggestion binary).
- **Grounding rate** = grounded suggestions / total suggestions.
- `perishable` and `missing` never count against grounding — they're honest flags, added
  to a shopping list.

**Bottle matching (`recommender/inventory_match.py`):** free-form, token-overlap based
(the model names bottles freely; a matcher checks ownership). Generic category nouns
(`bitters`, `vermouth`, `rum`, `gin`, …) are treated as non-matching tokens, so
"Peychaud's Bitters" does **not** match an owned "Angostura Bitters" on the shared word
"bitters" — a brand/qualifier token must overlap. Subcategory words (bourbon/rye/mezcal)
are *not* excluded, so generic "rye" still matches an owned "Rittenhouse Rye".

**Known limit (motivates Metric 2):** grounding measures *honesty about ownership*, not
*usefulness*. A drink that flags every ingredient `missing` is 100% grounded but uses
zero owned bottles — honest, but not makeable.

## Metric 2 — Makeable rate  *(implemented)*

Complements grounding. Definitions:
- `uses_inventory` — the suggestion has ≥1 `inventory` ingredient that matches an owned bottle.
- `makeable_now` — `uses_inventory` **and** zero `missing` ingredients.

Applies only to **open-ended** requests (occasion/mood). A user who explicitly demands a
named classic ("make a Mai Tai") accepts a shopping list, so named-drink scenarios are
exempt (`Scenario.open_ended = False`).

## Metric 3 — LLM-as-judge  *(implemented; run live; calibrated against human labels — P2)*

For the subjective dimensions deterministic checks can't see (`evals/judge.py`,
`JudgeVerdict`):
- `constraints_respected` (bool, strict — any violated constraint → false)
- `occasion_fit` (1–5)
- `recipe_plausibility` (1–5)
- `name_accurate` (bool — catches "a Boulevardier called a Negroni"; excluded from rate when absent)
- `companion_targeting` (1–5, omitted when no companions present)

`JudgeSummary` aggregates constraint pass-rate and average scores. The judge has been
**calibrated against human labels** (P2 — 16 suggestions labeled; see `RESUME_STORY.md`).

## Scenarios

`evals/fixtures.py` — each `Scenario` is `(id, request, inventory, note)` plus optional
property assertions (`expect_count`, `expect_min_grounded_rate`, `check_suited_for`). 14
scenarios total: normal cases, constraint-heavy cases, sparse/honest cases, an
**adversarial** group of named classics whose key ingredient isn't owned (Negroni w/o gin,
Sazerac w/o Peychaud's, Mai Tai bourbon-only, count=5 from 3 bottles) designed to tempt
the model into faking ownership, and two **companion** scenarios (opposite profiles, single
companion) that validate `suited_for` targeting.

Mock responses (`evals/mock_responses.py`) seed violations so the offline run exercises the
scorers; the live model is scored on the same scenarios.

## Running it

```bash
.venv/bin/python -m pytest -q                      # unit tests (scorers, matcher, parser, judge)
.venv/bin/python -m evals.run_evals                # offline, mock responses, zero tokens
.venv/bin/python -m evals.run_evals --live         # real model (needs ANTHROPIC_API_KEY)
.venv/bin/python -m evals.run_evals --live --judge # also run the LLM judge
.venv/bin/python -m evals.inspect <scenario_id>... # print the model's actual suggestions
```

Current numbers and their history live in `../RESUME_STORY.md` (metrics timeline).
