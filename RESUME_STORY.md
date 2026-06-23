# BarBack — Resume / Interview Story

Living notes capturing the narrative, decisions, and metrics for this project.
Purpose: a portfolio piece aimed at **AI/ML-leaning roles** (senior generalist SWE
as fallback). Built AI-deep, eval-first — *not* full-stack breadth — because 17
years of SWE already proves I can build CRUD; what this demonstrates is the
engineering discipline *around* an LLM.

---

## One-liner

An LLM cocktail recommender grounded in the user's actual bottle inventory, with a
deterministic **eval harness** that measures and protects recommendation quality.

## The metrics timeline (the spine of the story)

_All "mock" numbers are from offline runs with seeded-violation stubs — no tokens spent.
"Current" refers to the 12-scenario set including 4 adversarial named-classic scenarios added later._

| Milestone | Grounding | Makeable | Makeable-now | Notes |
|---|---|---|---|---|
| Mock baseline — original 8 scenarios | **64%** | — | — | Proved the scorer catches hallucinated ownership before spending a token. |
| **Live baseline** (claude-haiku-4-5), original 8 scenarios | **91%** | — | — | 10/11 grounded. Failure: model labeled honey/cinnamon as `pantry` (over-assumed on-hand). |
| After tightening the pantry system prompt | **100%** | — | — | Model now flags honey/spices as `perishable` ("grab these"). Real before/after. |
| Live + 4 adversarial classics added (Negroni w/o gin, Sazerac, Mai Tai, count=5 from 3 bottles) | **100% grounded** | — | — | Model flags, doesn't fake — substitutes or marks `missing`. But see below: grounding ≠ makeable. |
| Mock baseline — current 12-scenario set + makeable metric added | **53%** | **88%** | **50%** | Lower grounding% expected: adversarial scenarios drag the mock average down (they're designed to catch violations). Makeable 88% means most open-ended suggestions are anchored in ≥1 owned bottle. |
| **Live run** (claude-haiku-4-5, all 12 scenarios, + judge) | **100%** | **94%** | **75%** | JUDGE: constraints respected 74%, occasion fit 4.6/5, recipe plausibility 4.4/5, **name accuracy 58%** — model grounds correctly but misnames ~42% of drinks (e.g. calls a Boulevardier a "Negroni"). Next lever: name-accuracy prompt work or structured output with canonical name validation. |

## Engineering decisions worth talking about (the "why" matters more than the "what")

1. **Eval split: deterministic checks + LLM-as-judge.**
   - *Grounding rate* (primary metric) is pure set math — every ingredient must be
     an owned bottle, an allowed pantry staple, a declared perishable, or flagged
     missing. No LLM in the loop, so it's cheap, fast, and unarguable.
   - Subjective dimensions (constraint adherence, occasion fit, recipe plausibility)
     go to an **LLM-as-judge**. Split rationale: *verify mechanically what you can,
     judge only what you must.*
2. **Schema designed for measurability.** Each ingredient carries a `source`
   (`inventory` / `pantry` / `perishable` / `missing`). This turned grounding from
   a fuzzy NLP problem into deterministic set math — the single most important
   design choice.
3. **Free-form-first, on purpose.** The model names bottles freely and a matching
   layer checks ownership — which produces a *real baseline to improve from*.
   ID-constraining the inventory is a known lever held in reserve, not used up front
   (constraining away the failures would make the metric trivially 100% and delete
   the story).
4. **Mock-then-live development.** Built the entire pipeline + eval against canned
   responses (zero tokens), with deliberately-seeded violations so the scorer was
   provably working before any API spend. Live run cost pennies.
5. **Security decision (for when it gets a backend): DB-enforced RLS, not
   app-enforced `WHERE user_id`.** A forgotten filter in a multi-tenant app is a data
   breach; chose Supabase client + user JWT so row-level security actually fires.
   (Caught that raw asyncpg would silently bypass RLS, making the policies dead code.)

## "I measured, found, fixed" — the eval doing its job

The live baseline flagged one failure: given only bourbon, the model built a Hot
Toddy and labeled **honey, hot water, and cinnamon stick** as `pantry`.
- "Hot water" → a scorer normalization bug (water is water). Fixed.
- Honey / cinnamon → a *legitimate catch*: the model over-assumed specialty items
  the user may not have. Surfaced that my **pantry boundary was under-specified**.

This is the cleanest interview anecdote: the eval caught a real over-assumption, I
tightened the definition, and the metric moved — concrete evidence I treat LLM
output as something to be measured and engineered, not trusted.

## What inspecting the outputs revealed (grounding ≠ makeable)

Reading the actual live suggestions — not just the score — surfaced two things the
grounding metric structurally cannot see. (Also a matcher bug: "Peychaud's Bitters"
was matching an owned "Angostura Bitters" on the shared word "bitters" — fixed by
treating generic category nouns as non-matching tokens.)

- **Grounding can be satisfied by a useless drink.** Asked for a Mai Tai with only
  bourbon owned, the model returned a Mai Tai that honestly flagged rum/orgeat/curaçao
  as `missing` — **100% grounded, but it uses zero owned bottles.** Honest ≠ makeable.
  → Motivates a second deterministic metric: a **makeable rate** (an open-ended
  recommendation should be anchored in ≥1 owned bottle, not a pure shopping list).
- **Grounding can't judge correctness.** Asked for a Negroni without gin, it returned
  bourbon + Campari + sweet vermouth (a smart substitution — but that's a *Boulevardier*)
  and still **called it a "Negroni."** Grounded, but the name is wrong. → LLM-judge territory.

Strong signal alongside these: asked for 5 drinks from a 3-bottle bar, it returned five
distinct drinks each anchored on an owned spirit, no invented bottles.

**The takeaway line:** "grounding measures honesty about ownership, not usefulness — so
I added a makeable-rate metric and an LLM judge to cover the axes grounding can't."

## Prompt injection defense

User-controlled strings (bottle names, companion names, occasion text, seed likes)
all flow into the LLM context. Three layers of defense:

1. **Structured output** — the primary cage. Even if the model is confused by injected
   text, it can only emit valid `Recommendation` JSON. It cannot exfiltrate data or
   take actions outside the schema.
2. **`<user_data>` delimiter wrapping** — the system prompt tells the model that
   everything inside `<user_data>` tags is inert app data, never instructions.
   Standard prompt-injection mitigation: clear boundary between trusted instructions
   and untrusted user content.
3. **Input length caps** — `max_length=200` on occasion/mood, `max_length=100` on
   preference values. Limits blast radius of any injected payload.

The grounding scorer and LLM judge are a fourth layer: if injection caused the model
to recommend hallucinated bottles, grounding catches it; if it produced implausible
output, the judge catches it.

**Interview one-liner:** "The primary defense is structured output — injected content
can only produce valid `Recommendation` JSON, so the blast radius is limited to weird
drink descriptions, which the grounding scorer and LLM judge both catch."

## Interview-ready sentences

- "I tracked *grounding rate* as my primary metric — the percent of recommendations
  where every ingredient is something the user actually owns or is explicitly told
  to buy. It's deterministic, so it's defensible."
- "I split evaluation into deterministic checks for what I could verify mechanically
  and an LLM judge for the subjective parts."
- "I built and measured against mocks first, with seeded failures, so I knew the
  harness worked before spending a token."
- "The eval caught the model over-assuming pantry items; I tightened the grounding
  definition and the rate moved from 91% to 100%."
- "The primary defense against prompt injection is structured output — injected content
  can only produce valid `Recommendation` JSON, so the blast radius is limited to weird
  drink descriptions, which the grounding scorer and LLM judge both catch."

## Product framing — why a portfolio piece, not a business (yet)

The original idea was a consumer product: "Untappd / Vivino for cocktails" — log the
drinks you've tried and liked, get recommendations; the bartender's "I just know what
you'll want" trick as an app. It was stress-tested and **deliberately shelved as a
business** for now, for reasons worth being able to articulate:

- **Proven model, but the value isn't the recommender.** Untappd (beer) and Vivino
  (wine) prove the log→recommend model works — but they won on *frictionless logging +
  social/gamification*, not on recommendation quality. The recommender (the fun part) is
  the least important ~20%.
- **Cold-start / logging-friction trap.** The "I'm indecisive at a bar, surprise me"
  moment is exactly when the user has logged nothing and won't stop to journal. The value
  arrives only after work the user won't do.
- **Two different products.** Bar-goer (social discovery, Untappd-shaped) vs. home
  mixologist (inventory-based, Mixel-shaped) are different apps; building both finishes neither.
- **Cheapest test first.** The right validation is a Wizard-of-Oz run — ~10 people text
  their 5 favorite drinks, you reply with a recommendation, and you measure *unprompted
  second requests* — not building the app.

**Decision:** shelve the business question and build this as an **AI/ML portfolio piece**,
which is why it's scoped AI-deep (eval-first) rather than full-stack breadth. If the
business is ever revisited, the Wizard-of-Oz test above is the starting point — not more code.

## Persistence layer engineering (Phase 6 — added after the eval foundation)

**What was built:** Full multi-user backend — Supabase Auth + Postgres + FastAPI, a multi-tab
SPA frontend, and a complete test suite covering every endpoint.

**Key decisions and war stories:**

1. **`supabase-py` over `asyncpg` — a real footgun caught.** The original spec combined
   Supabase Auth (JWT + RLS) with raw `asyncpg`. Those two are silently incompatible:
   `asyncpg` connects as the service role, so `auth.uid()` is never set in the DB session
   and **every RLS policy becomes dead code.** A single forgotten `WHERE user_id` would
   be a cross-user data leak with no second line of defense. Caught this before writing
   a line of DB code; ADR-001 documents the decision and the why.

2. **Thread-safe Supabase client.** `supabase-py`'s PostgREST auth state is not
   thread-safe to mutate on a shared client. Solution: new `create_client()` per request,
   then `client.postgrest.auth(user_jwt)`. Costs a tiny bit of overhead; correct is worth it.

3. **JWT → `user_id` vs. JWT → DB.** A subtle latent bug found during P6.9: `get_current_user`
   returns the `sub` claim (a UUID), and all routers passed that to `DB(user_jwt)`. But
   `postgrest.auth()` needs the actual Bearer JWT, not the UUID. Tests missed it because DB
   is mocked; caught before deploy by reading the code. Fixed: routers now `Depends(bearer_scheme)`
   for the raw JWT, `Depends(get_current_user)` for validation.

4. **Atomic preference reversal via Postgres RPC.** Updating a companion's preference from
   "like" to "dislike" requires DELETE + INSERT. The supabase-py REST path can't do two-step
   operations atomically. Solution: `ON CONFLICT (companion_id, value) DO UPDATE SET type = ?`
   in a `SECURITY DEFINER` function — one round-trip, no TOCTOU race.

5. **`/sessions/active` route ordering.** FastAPI matches path parameters greedily —
   `GET /sessions/{id}` would capture "active" as a UUID param. Fixed by registering
   `/sessions/active` before `/{id}` in the router file. Documented in the spec.

6. **Defense-in-depth on `GET /sessions/{id}/drinks`.** Even with RLS, the application
   explicitly checks session ownership before calling `list_session_drinks`. Two independent
   layers must fail before a cross-user read succeeds.

**Test count:** 88 passing unit tests (no live Supabase), 3 live RLS isolation tests
(skipped without test credentials). Every endpoint has: auth-required test, happy path,
and relevant error paths (404, 409, 422).

---

## Structured outputs (P4 — completed)

**What changed:** replaced "ask for JSON + parse + retry" with `output_config.format` schema-guaranteed output.

- **`AnthropicClient.generate_structured(system, user, schema)`** — calls `messages.create()` with `output_config={"format": {"type": "json_schema", "schema": RECOMMENDATION_SCHEMA}}`. API guarantees response is valid JSON matching the schema; no parse-failure path.
- **`RECOMMENDATION_SCHEMA`** — hand-authored from `Recommendation`/`Suggestion`/`Ingredient` pydantic models with `additionalProperties: false` on every object node; unsupported constraints (min/max) absent by design.
- **`recommender.recommend()`** — tries `generate_structured` first (AnthropicClient); falls back to `generate` + retry for MockClient (detected via `hasattr`). Structured path raises immediately on failure rather than re-prompting, since a schema violation signals an API-level bug, not a model formatting slip.
- **Token capture** — `AnthropicClient` now reads `msg.usage.input_tokens` / `output_tokens` and stores them on `last_usage` after every call. Enables P10 telemetry and P1 cost comparison.
- **Model parameterization** — `AnthropicClient(model=...)` accepts any model ID; default stays `claude-haiku-4-5-20251001`. Enables P1 sweep.
- **Parse-failure rate:** before = theoretically non-zero (real retry happened once in testing). After = 0 — schema contract enforced at the API level.

**Interview line:** "I moved from 'ask for JSON and hope' to `output_config.format` — the API won't return a response that violates the schema. The retry loop still exists for mock/legacy clients, but the live path eliminated an entire failure mode."

## Multi-model sweep (P1 — completed)

**Goal:** measure whether spending more on a bigger model actually improves recommendation quality.

**Method:** `evals/sweep.py` ran all 14 eval scenarios through each model and recorded grounding%, makeable-now%, token counts, and cost. Judge skipped (offline-equivalent — same scenarios as the live judge run above).

| Model | Grounding | Make-now | Input tok | Output tok | Cost | Time |
|---|---|---|---|---|---|---|
| `claude-haiku-4-5-20251001` | **100%** | **84%** | 16,352 | 6,388 | **$0.0483** | 85.9s |
| `claude-sonnet-4-6` | 91% | 58% | 16,366 | 7,701 | $0.1646 | 157.9s |
| `claude-opus-4-8` | 91% | 58% | 20,961 | 9,497 | $0.3422 | 138.8s |

**Decision: stay on Haiku.** It wins on every measured dimension:
- Grounding: 100% vs 91% — the smaller model is *more* honest about ownership, not less.
- Make-now: 84% vs 58% — the bigger models over-specify. They suggest exotic ingredients (rum, curaçao, Aperol) even in constrained scenarios, producing grounded-but-not-makeable outputs. Haiku stays closer to what's actually in the bar.
- Cost: Haiku is 3.4× cheaper than Sonnet, 7.1× cheaper than Opus. No quality trade-off to compensate.
- Output tokens: Opus used 9,497 vs 6,388 for Haiku — 49% more tokens for worse make-now scores. Verbose ≠ accurate on this task.

**The insight worth articulating:** bigger models aren't always better — task shape matters. This is a constraint-satisfaction problem (use what's in inventory), not a creative writing or reasoning problem. Haiku, being more "literal," respects the constraints better; Sonnet and Opus pattern-match to "good cocktail recipes" and overreach. The eval harness is what revealed this — without it, the obvious call would be "use the best model."

**Engineering note:** one bug caught during sweep implementation — Opus 4.8+ rejects the `temperature` parameter (deprecated). Fixed by adding `_MODELS_WITHOUT_TEMPERATURE` frozenset and `_base_params()` helper that conditionally omits it. This is exactly the kind of silent breaking change a sweep harness catches automatically.

**Interview line:** "The sweep showed Haiku outperforms Opus on this task — it's both cheaper and better. Bigger models over-specify; they suggest great cocktails that need ingredients you don't own. Without the eval harness I wouldn't have known — the obvious engineering choice is always 'use the best model.'"

---

## RAG / retrieval (P3 — completed)

**What was built:**
- `scripts/fetch_cocktaildb.py` — fetched 426 canonical recipes from CocktailDB API into `data/cocktails.json`
- `retrieval/index.py` — embeds each recipe (name + ingredients + instructions[:200]) with `all-MiniLM-L6-v2` (sentence-transformers); caches 426×384 vectors to `data/cocktails.vectors.npy`
- `retrieval/search.py` — cosine similarity search; `search(query, k=5) -> list[Recipe]`
- `build_context()` gains `use_retrieval=True` — appends top-5 retrieved recipes as canonical naming references *outside* the `<user_data>` fence
- `run_evals.py` gains `--rag` flag for A/B comparison

**Retrieval quality:** `evals/retrieval_eval.py` — recall@10 = **80% (8/10)**. Two misses:
- "classic gin aperitivo bitter" → Negroni: vocabulary gap — the corpus recipe text doesn't use "aperitivo" or describe itself as bitter
- "gin lemon sour egg white" → Gin Fizz/Tom Collins: CocktailDB doesn't include egg white for these, so the query terms don't match

**A/B eval results (with/without RAG, same 14 scenarios):**

| Metric | No RAG | With RAG |
|---|---|---|
| Grounding | 95% | **100%** |
| Makeable-now | 68% | **79%** |
| Constraints respected | **82%** | 59% |
| Recipe plausibility | **4.7/5** | 4.1/5 |
| Name accuracy | **82%** | 55% |

**The unexpected finding:** RAG improved grounding and makeable-now but *hurt* name accuracy and constraint adherence. Diagnosed as over-anchoring — the model sees a canonical Negroni recipe with gin and either tries to use gin (violating constraints) or follows the canonical recipe too closely rather than adapting to the user's actual bar. Injecting recipes as inspiration works against a system designed for substitution.

**The honest conclusion:** RAG helps the "can I make this?" dimension (more owned bottles anchor the suggestions) but hurts the "does this respect my constraints?" dimension. For this use case, ingredient-coverage retrieval (set math) might be more appropriate than semantic retrieval — find recipes the user *can* make rather than recipes that are *similar* to what they asked for.

**Also notable:** name accuracy varied 55%–82% across runs in the same session with temperature=0.3. A single-run number isn't reliable for this dimension; need multiple runs and averaging, or structured outputs that constrain naming.

**Interview line:** "RAG improved grounding 5pp and makeable-now 11pp, but name accuracy dropped 27pp — the eval caught it immediately. The model over-anchored on canonical recipes: seeing a Negroni recipe made it more likely to call things Negronis, not less. That's the kind of non-obvious failure you only find if you measure."

**Fix — prompt engineering + reframed RAG:**
Two changes made together:
1. Added a `NAMING RULE` to the system prompt: substituting the base spirit means giving the drink a new name, with explicit examples (bourbon+Campari+vermouth = Boulevardier, not Negroni).
2. Changed RAG injection framing from "inspiration" to "naming reference only" — explicit instruction not to borrow the classic name if the base spirit differs.

Results after both fixes:

| Metric | Old no-RAG | Old RAG | New no-RAG | New RAG |
|---|---|---|---|---|
| Grounding | 95% | 100% | **100%** | **100%** |
| Makeable-now | 68% | 79% | **79%** | **79%** |
| Constraints | 82% | 59% | **86%** | 73% |
| Recipe plausibility | 4.7/5 | 4.1/5 | **4.9/5** | 4.5/5 |
| Name accuracy | 82% | 55% | 64% | **73%** |

RAG name accuracy recovered from 55% → 73% with the reframing. No-RAG improved on all dimensions except name accuracy (82% → 64%), likely due to run-to-run variance — these metrics have ±15pp noise at single-run level. RAG still trails no-RAG on constraints (73% vs 86%), suggesting canonical recipes occasionally pull the model off constrained scenarios.

**The full story arc:** identified the RAG regression with the eval → diagnosed over-anchoring → fixed the framing → measured improvement. Three iterations, each time the harness told us what changed.

---

## Judge calibration results (P2)

Human labels (16 suggestions) vs LLM judge, keyed on `suggestion_hash` (SHA256[:8] of sorted ingredient names+sources — stable across renames, invalidates on recipe change):

| Dimension | Agreement |
|---|---|
| `constraints_respected` | 80% (4/5 pairs) |
| `name_accurate` | **56%** (9/16) — judge too lenient |
| `occasion_fit` | MAE=0.62, exact 50% — you gave all 5s, judge more conservative |
| `recipe_plausibility` | MAE=0.50, exact 69% — judge missed missing bitters/absinthe |
| `companion_targeting` | 100% (1/1) |

Key finding: `name_accurate` 56% agreement — the judge passed "Mezcal Negroni", "Bourbon Neat on the rocks", "Old Fashioned without bitters" as correct. Judge prompt was tightened post-calibration with explicit rules: substituting base spirit = false, missing canonical ingredients = false, rubric added to `recipe_plausibility`.

**Interview line:** "I didn't trust the judge until I validated it. Calibration caught that it was 56% agreement on name accuracy — systematically too lenient on creative names borrowing classic labels. I tightened the prompt and re-ran."

## Observability / tracing (P5)

`evals/tracing.py` — `TraceRecord` dataclass (ts, model, scenario_id, input_tokens, output_tokens, latency_ms, call_type); `write()` appends JSONL non-fatally. `run_evals.py` gains `--trace [PATH]`. `evals/trace_summary.py` prints aggregates by model and call_type.

Sample from a full judge run (14 scenarios, 22 suggestions):

```
36 calls  |  input: 33,234 tok  |  output: 8,457 tok  |  avg latency: 2,589ms

By call type:
  recommend   14 calls   18,466 in   6,395 out   4,403ms avg
  judge       22 calls   14,768 in   2,062 out   1,435ms avg
```

Recommend calls are 3× slower and use 4× more output tokens than judge calls — useful for cost modeling if you ever scale to many users.

## Open decisions / next steps

- [x] **Pantry boundary:** decided — honey/cinnamon stay as legitimate "grab these"
  flags (kept the metric honest). Fixed via system-prompt tightening, not by widening
  the allowlist. Also fixed the hot-water normalization bug in the scorer.
- [x] **Adversarial scenarios added** (Negroni/Sazerac/Mai Tai/count=5). Live grounding
  stayed 100% — the model flags rather than fakes. Also fixed a matcher false-positive
  (generic "bitters"/"vermouth"/etc. no longer carry a match alone).
- [x] **Makeable-rate metric** implemented. `uses_inventory` = ≥1 owned bottle anchors the
  drink; `makeable_now` = uses_inventory AND zero `missing` ingredients. Correctly re-validates
  inventory claims to catch hallucination (model claiming a bottle you don't own still fails).
  Mock baseline: MAKEABLE 88%, MAKEABLE-NOW 50% across open-ended scenarios.
- [x] **FastAPI + single-page frontend** deployed locally. `POST /recommend`, `GET /inventory`,
  rate-limited (10/min per IP), input-length capped, XSS-safe frontend. Ready for Railway deploy.
- [x] **Live eval run** complete. GROUNDING 100%, MAKEABLE 94%, MAKEABLE-NOW 75%.
  JUDGE: constraints 74%, occasion fit 4.6/5, plausibility 4.4/5, **name accuracy 58%** —
  the model grounds correctly but misnames ~42% of drinks. Confirmed in production: "movie night"
  request returned a Boulevardier (correct) and a "Negroni" made with mezcal + dry vermouth
  (neither gin nor sweet vermouth — not a Negroni by any definition). Grounding: 100%. Name: wrong.
  This is the clearest next improvement target and a live demo of exactly why the judge exists.
- [x] **Railway deploy** complete. Live URL: https://barback-production.up.railway.app
  (`railway.toml` start command + ANTHROPIC_API_KEY set in Railway dashboard).
