# Build Plan — Drink Suggester

Execution plan broken into atomic subtasks. Each is small enough to do in one sitting,
names the exact file(s), and ends with a **Verify** step. Work top-to-bottom within a task.

**Status legend:** `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` blocked
**🧑 = needs a human** (account/auth/browser/secrets — a model writes the code and hands over the command, but cannot click through). When an executor model hits a 🧑 step, stop and hand it to the user.
When you finish a subtask, change its box and add a one-line note in _italics_ after it.
Keep `RESUME_STORY.md` in sync when a metric or decision changes (see memory).

**Environment:** Python 3.14, venv at `.venv`. Tests: `.venv/bin/python -m pytest -q`.
Evals: `.venv/bin/python -m evals.run_evals [--live] [--judge]`.
Git: use the absolute binary `/opt/homebrew/bin/git` (the shell `git` wrapper is broken here).

---

## Task 1 — Makeable-rate metric (deterministic)  ·  Status: done

Goal: a metric that complements grounding. Grounding = "honest about ownership";
makeable = "actually buildable from owned bottles." Closes the all-`missing` Mai Tai gap.

- [x] **1.1 Decide + document the definition** in a comment at the top of the new file:
      `uses_inventory` = suggestion has ≥1 ingredient with `source == inventory` that matches an owned bottle;
      `makeable_now` = `uses_inventory` AND zero `missing` ingredients.
      _Definitions documented in module docstring of `evals/makeable.py`._
- [x] **1.2 Add `open_ended: bool = True` field** to the `Scenario` dataclass in `evals/fixtures.py`.
      Set `open_ended=False` on the four named-drink scenarios (negroni_no_gin, sazerac_no_peychauds,
      mai_tai_bourbon_only) — a user who *demands* a specific classic accepts a shopping list.
      Leave `high_count_pad` and all occasion/mood scenarios `open_ended=True`.
      _Field added to `Scenario`; `open_ended=False` set on `negroni_no_gin`, `sazerac_no_peychauds`, `mai_tai_bourbon_only`._
- [x] **1.3 Create `evals/makeable.py`** with: `is_makeable(suggestion, inventory) -> bool` (uses_inventory),
      `is_makeable_now(suggestion, inventory) -> bool`, and `score(suggestions, inventory) -> MakeableReport`
      (dataclass with `.uses_inventory_rate` and `.makeable_now_rate`). Reuse `recommender.inventory_match.match_bottle`.
      _`evals/makeable.py` created with all three functions and `MakeableReport` dataclass._
- [x] **1.4 Create `tests/test_makeable.py`**: all-`missing` Mai-Tai-shaped suggestion → not makeable;
      all-`inventory` Boulevardier-shaped → makeable_now; 1 owned + 1 missing → uses_inventory True, makeable_now False.
      **Verify:** `.venv/bin/python -m pytest -q` all green.
      _4 tests added; all 29 tests pass._
- [x] **1.5 Wire into `evals/run_evals.py`**: compute makeable over `open_ended` scenarios only;
      print `MAKEABLE RATE` and `MAKEABLE-NOW RATE` lines under `GROUNDING RATE`.
      **Verify:** `.venv/bin/python -m evals.run_evals` prints both, no crash.
      _Wired; fixed is_makeable_now to also re-validate inventory claims (hallucination bug); mock: MAKEABLE 88%, MAKEABLE-NOW 50%; 30 tests green._
- [x] **1.6 Run live once**: `.venv/bin/python -m evals.run_evals --live`. Record grounding + makeable
      numbers in `RESUME_STORY.md` metrics table. Commit (see git note above).
      _Live: GROUNDING 100%, MAKEABLE 94%, MAKEABLE-NOW 75%. Recorded in RESUME_STORY + README._

## Task 2 — Run the LLM judge live  ·  Status: done

Goal: produce the quality numbers grounding can't (built + unit-tested, never run live).

- [x] **2.1 Sanity-read `evals/run_evals.py`** `--judge` branch — confirm it calls `judge_suggestion`
      per suggestion with a live `AnthropicClient` and prints the `JudgeSummary` line.
      _Confirmed: lines 80-85 collect verdicts per suggestion, summarize at end, prints JudgeSummary._
- [x] **2.2 (Optional, recommended) add a `name_accurate` bool** to `JudgeVerdict` in `evals/judge.py`
      + one line in `JUDGE_SYSTEM` ("if the drink's name doesn't match its actual recipe, set false").
      Add a `JudgeSummary.name_accuracy_rate`. Add a unit test in `tests/test_judge.py`.
      **Verify:** `.venv/bin/python -m pytest -q` green. _(Catches "Boulevardier called a Negroni".)_
      _Done; name_accurate=None when absent (excluded from rate to avoid inflation); prompt clarified for invented names; name_accuracy_n denominator exposed; 34 tests green._
- [x] **2.3 Run** `.venv/bin/python -m evals.run_evals --live --judge`. Capture constraint pass rate,
      occasion fit, plausibility (and name accuracy if 2.2 done).
      _constraints 74%, occasion fit 4.6/5, plausibility 4.4/5, name accuracy 58% (19/19 assessed)._
- [x] **2.4 Record** the judge numbers in `RESUME_STORY.md`; commit.
      _Recorded; name accuracy 58% flagged as next improvement target._

## Task 3 — Deploy a thin vertical slice (live URL)  ·  Status: done

Goal: a clickable demo. Keep it minimal — no DB, no auth, hardcoded inventory for v1.

- [x] **3.1 Add deps** to `requirements.txt`: `fastapi`, `uvicorn[standard]`. `pip install -r requirements.txt`.
      _fastapi 0.138.0, uvicorn 0.49.0 installed._
- [x] **3.2 Create `app/main.py`**: FastAPI app; `POST /recommend` accepts a `RecommendRequest`
      (import from `recommender.schemas`), builds an `AnthropicClient`, calls `recommender.recommender.recommend`
      with a hardcoded inventory imported from `evals.fixtures.INVENTORY`, returns the `Recommendation`.
      Add `GET /inventory` returning that fixture inventory. Add CORS allowing the frontend origin.
      Load `.env` at startup.
      _Created; CORS wildcard for v1; 503 if API key missing._
- [x] **3.3 Verify locally:** `.venv/bin/uvicorn app.main:app --reload`, then curl.
      _Import + route registration verified (API key needed for actual /recommend call — deferred to live run)._
- [x] **3.4 Create `app/static/index.html`**: one screen — occasion text input, mood input, count, a
      "Suggest" button that `fetch`es `POST /recommend` and renders cards (name, ingredients with source
      badges, steps, why). Vanilla JS, no build step.
      _Created; ingredient source badges color-coded (inventory/pantry/perishable/missing)._
- [x] **3.5 Serve static** from FastAPI (`StaticFiles` mounted at `/`). Verify the page works against local API.
      _StaticFiles uses absolute path (Path(__file__).parent/static); rate limiter (20/min global, 10/min /recommend); RecommendationError → 502; input max_length 200 + count 1-10; frontend XSS-safe via txt() escaping + 30s fetch timeout; 34 tests green._
- [x] **3.6 🧑 Deploy to Railway**: deployed. URL: https://drinksuggesterproject-production.up.railway.app
- [x] **3.7 🧑 Verify the live URL** end-to-end from a browser (human). Then put the URL in
      `README.md` and `RESUME_STORY.md`. Commit.
      _Verified. Real output: Boulevardier (correctly named, all inventory) + "Negroni" using mezcal/dry vermouth — live demonstration of the 58% name accuracy finding._

## Task 4 — README that tells the story  ·  Status: done

- [x] **4.1 Overview section**: one paragraph — what it is, who it's for, the eval-first angle. _(done in README.md)_
- [x] **4.2 Architecture diagram**: ASCII diagram in README. _(upgrade to mermaid optional)_
- [x] **4.3 "Eval design" writeup**: summarized in README, fully specified in `docs/eval-spec.md`.
      _Metrics timeline table inlined into README with mock baseline numbers; makeable definition expanded._
- [x] **4.4 "Security decision" writeup**: RLS-at-the-DB vs app-enforced `WHERE user_id`; why asyncpg would
      silently bypass RLS. _(Read `docs/adr-001-data-isolation.md` and summarize it — do not invent the rationale.)_
      _Written from ADR verbatim; interview one-liner included._
- [x] **4.5 Setup/run section**: venv, install, pytest, run_evals (mock + live). _"Run the app" section added after Task 3._
- [x] **4.6 Live demo link** + a screenshot. Commit.
      _Live demo URL in README + RESUME_STORY. Screenshot: Boulevardier + "Negroni" (mezcal/dry vermouth) — live name accuracy failure._

## Task 5 — CI gate on the evals  ·  Status: in progress

- [x] **5.1 Create `.github/workflows/ci.yml`**: trigger on push/PR; Python 3.12; `pip install -r requirements.txt`.
      _Created at .github/workflows/ci.yml._
- [x] **5.2 Run `pytest -q`** as a required step.
      _Included in ci.yml._
- [x] **5.3 Run `python -m evals.run_evals`** (mock mode — no API key in CI). **Added `--strict` flag**
      that exits non-zero if any property assertion fails; used in CI.
      _`--strict` added to run_evals.py; exits 0 when all pass, 1 on failures._
- [x] **5.4 🧑 (Optional) nightly live eval**: `.github/workflows/nightly-eval.yml` written (Python 3.14,
      pytest + live eval + judge, 10-min timeout, fork guard). Human step: add `ANTHROPIC_API_KEY` repo secret.
- [ ] **5.5 Add a CI status badge** to `README.md`. Commit. _(blocked on repo having CI run first)_

---

## Cross-cutting reminders for the executor
- Commit at each "Verify"-passing subtask (small commits). Co-author trailer required; absolute git binary.
- Never commit `.env`. `.venv`, `__pycache__`, `.pytest_cache` are already gitignored.
- If a subtask's acceptance check fails, mark it `[!]` with the error and stop — don't guess past it.
- When a step is marked 🧑, do the model-doable part (write the code/YAML/command), then hand the
  interactive part (login, dashboard secret, browser check) to the user — don't fake it as done.

---

## Phase 2 — after the 5 (ordered by AI/ML-resume signal)

Same rules as Phase 1: atomic subtasks, exact files, a Verify step, commit at each green step.

### P1 — Multi-model sweep  ·  Status: in progress (needs live run P1.4)
Goal: benchmark Haiku/Sonnet/Opus on the eval and choose one, with cost/latency in the picture.
- [x] **P1.1 Parameterize the model.** In `recommender/llm.py`, add a `model` arg to `AnthropicClient.__init__`
      (default the current Haiku id). In `evals/run_evals.py` add `--model <id>` and pass it through.
      _Done as part of P4; run_evals.py updated with `--model` flag and dynamic mode line._
- [x] **P1.2 Capture usage.** `AnthropicClient.last_usage: UsageStats` captures `input_tokens`/`output_tokens`
      per call. Price table `PRICE_TABLE` in `evals/sweep.py`.
      _Done as part of P4; `last_usage` recorded in both `generate()` and `generate_structured()`._
- [x] **P1.3 Create `evals/sweep.py`.** For each model in a list, run all scenarios (grounding + makeable +
      optionally judge), accumulate tokens + wall-clock, print one row per model.
      _Created `evals/sweep.py`; `--models` flag; `--judge` flag; PRICE_TABLE for Haiku/Sonnet/Opus._
- [ ] **P1.4 🧑 Run the sweep live**: `.venv/bin/python -m evals.sweep [--judge]`. Record output.
- [ ] **P1.5 Record** the comparison table + a one-paragraph "why I chose X" in `RESUME_STORY.md`; commit.
- [ ] **P1.6 Set the chosen model** as the default in `AnthropicClient` (or via env); note the decision. Commit.

### P2 — Judge calibration  ·  Status: not started
Goal: check whether the LLM judge agrees with a human — don't trust a judge you haven't validated.
- [ ] **P2.1 🧑 Build a labeled set.** Create `evals/judge_labels.json`: ~15 `{scenario_id, suggestion_name,
      constraints_respected, occasion_fit, recipe_plausibility}` rows labeled **by the user** from real outputs
      (use `python -m evals.inspect` to see them).
- [ ] **P2.2 Create `evals/calibrate_judge.py`.** Re-run the judge on those same outputs; compute agreement:
      exact-match rate for the boolean, mean-absolute-error for the 1–5 scores. Print per-dimension agreement.
- [ ] **P2.3 Run it** (`--live`); record agreement + the cases where judge and human disagree.
- [ ] **P2.4 If agreement is weak**, revise `JUDGE_SYSTEM` in `evals/judge.py`, re-run, track the delta.
      **Verify:** `pytest -q` still green.
- [ ] **P2.5 Record** agreement numbers + the "I validated my judge against human labels" note in `RESUME_STORY`; commit.

### P3 — Retrieval / RAG  ·  Status: not started
Goal: ground/inspire suggestions in a corpus of real recipes, with a retrieval-quality metric.
- [ ] **P3.1 Decide the stack** (write the choice in a comment): local `sentence-transformers` embeddings +
      numpy cosine (no extra API key) vs. Voyage AI embeddings (Anthropic-recommended, needs a key). Default to local.
- [ ] **P3.2 🧑 Source the corpus.** Create `data/cocktails.json` — ~150–300 classic recipes
      `{name, ingredients[], instructions, tags[]}`. May need a human to pick/clean a public dataset.
- [ ] **P3.3 Create `retrieval/index.py`.** Embed each recipe (name+ingredients+tags) once; cache vectors to
      `data/cocktails.vectors.npy`. **Verify:** running it twice doesn't re-embed (cache hit).
- [ ] **P3.4 Create `retrieval/search.py`.** `search(query: str, k=5) -> list[Recipe]` via cosine similarity.
      Add a unit test in `tests/test_retrieval.py` (a "smoky agave" query returns mezcal/tequila drinks).
- [ ] **P3.5 Wire into the recommender** behind a `use_retrieval: bool` flag: retrieve top-k for the
      occasion/mood/inventory and add them to the context as inspiration (still grounded to owned bottles).
- [ ] **P3.6 Add a retrieval-quality metric.** Small labeled query→expected-recipe set; compute recall@k.
      Add to `evals/` and to `run_evals` output.
- [ ] **P3.7 Run eval with/without retrieval**; compare grounding/makeable/judge + recall@k; record; commit.

### P4 — Structured outputs via the API  ·  Status: done
Goal: replace "ask for JSON + parse + retry" with schema-guaranteed output (Haiku 4.5 supports it).
- [x] **P4.1 Read the structured-outputs section** of the `claude-api` skill (`output_config.format` /
      `messages.parse`); confirm the exact Python call shape before coding.
      _Confirmed: use `output_config={"format": {"type": "json_schema", "schema": ...}}` on `messages.create()`._
- [x] **P4.2 Generate the schema** from the `Recommendation` pydantic model (`model_json_schema()`); strip
      unsupported constraints (min/max, etc.) per the skill's limitations list.
      _Schema hand-authored in `RECOMMENDATION_SCHEMA` const in `recommender/recommender.py`; all objects have `additionalProperties:false`; no min/max used._
- [x] **P4.3 Add a structured path** to `AnthropicClient` — `generate_structured(system, user, schema)` using
      `output_config={"format": {"type": "json_schema", "schema": schema}}`. Also added `model` param and `last_usage: UsageStats | None` (input+output token capture).
      _Done in `recommender/llm.py`._
- [x] **P4.4 Switch `recommender.recommend`** to the structured path; keep the JSON-fence parse as a fallback
      for `MockClient` (detected via `hasattr(llm, "generate_structured")`).
      _Done in `recommender/recommender.py`._
- [x] **P4.5 Track parse-failure rate** before/after (should drop to ~0). Added 2 unit tests: structured path
      preferred, structured path raises cleanly on bad JSON. **Verify:** 36 offline tests + mock evals pass.
      _6 recommender tests pass; 36 total offline; mock evals all assertions pass._
- [x] **P4.6 Record** in `RESUME_STORY`; commit.

### P7 — Session history + verdict browser  ·  Status: done (P7.3 deferred — schema decision pending)
Goal: let the user review past sessions and manage verdicts for themselves and companions.
- [x] **P7.1 Add "History" tab** to the SPA. On tab-click, calls `GET /sessions?limit=50` and renders
      collapsible session rows: occasion, date, companion names (cross-referenced from loaded companions), active/ended state.
      _Done._
- [x] **P7.2 Expanded session view** — clicking a session row fetches `GET /sessions/{id}/drinks`;
      renders each drink with a verdict emoji badge (👍/😐/👎). No fetches until expanded.
      _Done._
- [~] **P7.3 Companion verdicts in session view** — deferred: per-companion verdict requires a new
      `companion_drink_verdicts` table or JSONB column on `session_drinks`. Design decision not made.
      Session view currently shows which companions were present (from `session_companions` data already
      included in `GET /sessions` response). Per-companion rating left for a later schema migration.
- [x] **P7.4 Companion exposure history** — "History" button added to each companion row in the
      Companions tab; expands a panel showing all drinks the companion was present for + their verdict.
      `GET /companions/{id}/history` returns `[{id, session_id, name, verdict, created_at}]`.
      `db.get_companion_history()` queries `session_companions` then `session_drinks`.
      _Done: endpoint + DB method + frontend panel._
- [x] **P7.5 Tests** — 3 new tests for `GET /companions/{id}/history` (happy path, empty, 404).
      **Verify:** 39 offline tests + 16 companion tests pass.
      _Done._

### P8 — Inventory category filtering  ·  Status: done
Goal: filter the inventory list by category with a whiskey super-group.
- [x] **P8.1 Add a category filter bar** above the bottle list: All · Whiskey (group) · Bourbon · Scotch ·
      Rum · Tequila · Mezcal · Gin · Vodka · Liqueur · Vermouth · Bitters · Other.
      Whiskey group = `{bourbon, scotch, rye, whiskey, irish, japanese, tennessee}`.
      Other = anything not in any named chip's category set.
      _Done; filter bar HTML + CSS chips added._
- [x] **P8.2 Filter client-side** — `_matchesFilter(bottle)` applied to `bottles` array before pagination.
      Page reset to 0 on filter change. Filtered count shown in pagination info (e.g. "5 of 23 bottles").
      _Done._
- [x] **P8.3 Active filter state** — gold highlight on active chip; All is default.
      Filter cleared (reset to All) when new bottle is added so new bottle is always visible.
      _Done._

### P9 — Per-companion recommendation targeting + evals  ·  Status: done
Goal: when companions are present, tag each suggestion with who it's suited for; add eval coverage.
- [x] **P9.1 Extend `Suggestion` schema** — `suited_for: list[str]` added to `recommender/schemas.py`;
      `RECOMMENDATION_SCHEMA` updated with the new field in `recommender/recommender.py`.
      _Done._
- [x] **P9.2 Update the system prompt** — `recommender/context.py` instructs the model to populate
      `suited_for` with exact companion names + "me"; empty list = suits everyone.
      _Done._
- [x] **P9.3 Render `suited_for` in the frontend** — chips below each card: "For: Alex Sam".
      _Done in `app/static/index.html` → `renderCard()`._
- [x] **P9.4 Add eval scenarios with companions** — `companion_smoke_sweet` (two companions with
      opposite profiles) and `companion_bitter_only` (single companion) added to `evals/fixtures.py`.
      `check_suited_for: True` property: asserts all names are "me" or a companion name.
      Mock responses added to `evals/mock_responses.py` with correct `suited_for` values.
      _All 14 scenarios pass assertions._
- [x] **P9.5 Add `companion_targeting` judge dimension** — `JudgeVerdict.companion_targeting: int | None`
      (1–5, omitted when no companions). `JudgeSummary.avg_companion_targeting` + `companion_targeting_n`.
      `build_judge_prompt()` now includes companion likes/dislikes and `suited_for` in the prompt.
      `run_evals.py` prints companion targeting score when available.
      _5 new judge tests pass._
- [x] **P9.6 Tests** — 5 new judge tests (companion_targeting parses, none when absent, summary avg,
      none when all absent, prompt includes profiles). 57 offline tests + mock evals pass.
      _Done._

### P10 — Recommendation telemetry on sessions  ·  Status: done
Goal: capture token cost, latency, and bar size per recommend call. Most identifying
data (who/when/what/companions/drinks) already lives in sessions + session_drinks.
Only 4 new columns needed — no separate table.

**What's already covered by sessions:**
- who/when/what: `user_id`, `created_at`, `occasion`, `mood` ✓
- companions: `session_companions` (count = `COUNT(session_companions)`) ✓
- drink results: `session_drinks` ✓

**4 new columns on `sessions`:**
```
bottle_count   int   -- snapshot of active bottle count at time of call
input_tokens   int   -- accumulated across all recommend calls into this session
output_tokens  int   -- accumulated (sessions can have >1 recommend call)
latency_ms     int   -- latency of the most recent recommend call
```
`bottle_count` is a snapshot, not a FK — the bar changes over time.
`input_tokens` / `output_tokens` accumulate on repeat calls into the same session
rather than overwriting, so the session total stays accurate.

- [x] **P10.1 Migration** — `supabase/migrations/20260623000000_session_telemetry.sql`:
      `ALTER TABLE sessions ADD COLUMN IF NOT EXISTS bottle_count/input_tokens/output_tokens/latency_ms`.
      Existing rows get NULL (telemetry is best-effort).
      _Done (🧑 apply via `supabase db push`)._
- [x] **P10.2 Capture tokens in `AnthropicClient`** — done in P4; `last_usage: UsageStats | None`
      set after every `generate()` / `generate_structured()` call.
      _Done._
- [x] **P10.3 Capture latency + write telemetry** — `app/main.py` wraps `recommend()` with
      `time.perf_counter()`. `db.update_session_telemetry()` accumulates tokens (read + add
      prior session total) and overwrites `bottle_count`/`latency_ms` with latest call.
      Non-fatal: `logging.exception` + continue if DB write fails.
      _Done._
- [x] **P10.4 Stats endpoint** — `GET /sessions/stats` (registered before `/{id}`) returns
      `{total_sessions, total_input_tokens, total_output_tokens, avg_latency_ms, avg_bottle_count}`.
      Python-side aggregation; NULL rows excluded from averages.
      _Done._
- [x] **P10.5 Tests** — telemetry written when `last_usage` set; telemetry failure non-fatal (200 still returned);
      stats returns correct aggregates; `/sessions/stats` not matched as session id.
      **Verify:** 87 offline tests pass.
      _Done._

### P11 — In-session memory (LLM + UI)  ·  Status: done
Goal: stop the LLM from repeating drinks already shown this session, and show all session drinks
in the UI instead of replacing them on each suggest call.

- [x] **P11.1 Schema** — add `SessionDrinkFeedback(name, verdict)` and two optional fields
      (`already_suggested: list[str]`, `session_feedback: list[SessionDrinkFeedback]`) to
      `RecommendRequest` in `recommender/schemas.py`. Defaults to `[]` so all existing callers work.
      _Done._
- [x] **P11.2 Prompt** — add two new blocks at the bottom of `build_context()` in
      `recommender/context.py`, inside `<user_data>`:
      "Drinks already suggested this session — do NOT suggest these again" and
      "Feedback from this session" (non-neutral verdicts only).
      _Done._
- [x] **P11.3 Wire in main.py** — in `app/main.py`, move session get/create BEFORE the
      `recommend()` call; fetch `db.list_session_drinks(session_id)` and populate
      `req.already_suggested` and `req.session_feedback` before passing req to `recommend()`.
      _Done._
- [x] **P11.4 UI accumulation** — in `app/static/index.html`:
      (a) Add `activeVerdict` param to `renderCard()` — pre-marks the active verdict button.
      (b) After each suggest call, render ALL session drinks (new batch at top, prior batch below
          a `──── earlier this session ────` divider using the already-fetched `sessionDrinks`).
      (c) Add `.session-divider` CSS style.
      (d) Remove the premature `results.innerHTML = ''` clear at the top of the submit handler.
      _Done._
- [x] **P11.5 Verify** — `pytest -q` green; manual test: two suggest calls in same session show
      no duplicates and both batches visible; rated drink shows active verdict badge on redraw.
      _91 tests pass; mock evals baseline holds (all assertions pass)._

### P5 — Observability / tracing  ·  Status: not started
Goal: log every LLM call so cost/latency/quality is inspectable, not guessed.
- [ ] **P5.1 Define a trace record** (dataclass): `ts, model, scenario_id, input_tokens, output_tokens,
      latency_ms, grounded, makeable`.
- [ ] **P5.2 Add a tracing hook.** In `run_evals` (or a wrapper around the client), write one JSONL line per
      call to `traces/eval-<timestamp>.jsonl`. Gitignore `traces/`.
- [ ] **P5.3 Create `evals/trace_summary.py`.** Read a JSONL file; print aggregates (calls, total/avg tokens,
      avg/p95 latency, est cost, grounding/makeable rates). **Verify:** runs on a sample trace.
- [ ] **P5.4 (optional) tiny dashboard:** a static `traces/view.html` that loads the JSONL and renders a table. Skippable.
- [ ] **P5.5 Record** a sample summary in `RESUME_STORY`; commit.

### P6 — The real backend (breadth)  ·  Status: not started
Goal: multi-user persistence. **Follow `docs/adr-001-data-isolation.md` — Supabase client + user JWT, NO asyncpg.**
- [x] **P6.0 Write `docs/backend-spec.md`** — the authoritative backend spec. Must cover: data model
      (inventory, companions, sessions, session_drinks), endpoint surface, and explicitly resolve each of these
      known pitfalls: the **error-body contract** (match FastAPI's `{detail}` or add handlers), **pagination**
      (`limit`/`offset` everywhere or nowhere — pick one), a **unique key** for upsert/dedup (e.g. `UNIQUE(user_id, name)`),
      the **companion-feedback verdict→like/dislike rule**, and a concrete definition of **"current session"**.
      _Written + reviewed + revised. Key fixes: RPC for atomic preference reversal (ON CONFLICT DO UPDATE); partial unique index for one-open-session-per-user; /sessions/active not /sessions/current (routing conflict); cross-user companion guard documented; PUT /companions/{id} added; GET /sessions/{id} added; trigger statements completed._
- [ ] **P6.1 🧑 Create the Supabase project**; collect URL, anon key, service key, JWT secret (human).
- [x] **P6.2 Write `backend/migrations/001_init.sql`** from the spec: tables + `UNIQUE(user_id, name)` where
      needed + RLS policies (`auth.uid() = user_id`) + `updated_at` trigger.
      _Written. Includes partial unique index for one-open-session-per-user, RLS on all 6 tables, upsert RPCs, idempotent (DROP IF EXISTS on policies/triggers)._
- [x] **P6.3 Apply the migration** via `supabase db push` (automated via CLI).
      _Linked project jnifjkmnoudeuprpzzge; migration 20260622000000_init.sql applied cleanly._
- [x] **P6.4 Auth dependency:** FastAPI `get_current_user` that verifies the Supabase JWT locally against the
      JWT secret and returns `user_id`; 401 on invalid. Unit-test with a signed test token.
      _backend/auth.py; 7 tests (valid, expired, wrong secret, wrong audience, service_role bypass, missing env var 503, missing sub); 41 tests green._
- [x] **P6.5 Data layer via `supabase-py` carrying the user JWT** (NOT asyncpg — per ADR). One thin module.
      _backend/db.py; DB class; new client per request (thread-safe); postgrest.auth(user_jwt) so RLS fires; covers all 6 tables + 2 RPCs; 41 tests green._
- [x] **P6.6 Inventory endpoints** (GET/POST/PUT/DELETE, soft-delete via `is_active`). Tests: auth required, 404/403.
      _`backend/routers/inventory.py` + 8 tests; fixed `patch` → `app.dependency_overrides`; bare `raise` → 500; 49 tests green._
- [x] **P6.7 Companions endpoints** + feedback (implement the verdict→like/dislike rule from the spec). Tests.
      _`backend/routers/companions.py` (13 tests) + `backend/routers/session_drinks.py` (8 tests); fuzzy bottle→category resolution via `match_bottle`; bumped bottle limit to 1000 to avoid silent truncation; 71 tests green._
- [x] **P6.8 Sessions + session_drinks endpoints**; implement "current session" per the spec. Tests.
      _`backend/routers/sessions.py` (11 tests); `/sessions/active` registered before `/{id}` to prevent routing conflict; added ownership guard on `GET /{id}/drinks`; 82 tests green._
- [x] **P6.9 Point `/recommend` at the user's real inventory** (replace the hardcoded fixture from Task 3).
      _`app/main.py` overhauled: all routers wired, real DB inventory fetch, session lifecycle (create/reuse), drinks saved to session_drinks, `X-Session-Id` header; fixed JWT vs user_id bug in all routers' `_db`; 6 endpoint tests; 88 tests green._
- [x] **P6.10 Frontend:** login, inventory manage, companions, sessions, recommend screen (extend Task 3's page).
      _Multi-tab SPA with Supabase JS auth, inventory CRUD, companions + preference viewer, recommend + verdict buttons; `/config` endpoint exposes public keys; browser UI untested (requires live Supabase)._
- [x] **P6.11 RLS isolation test:** two users; confirm user A cannot read/write user B's rows.
      _`tests/test_rls_isolation.py`; 3 tests (read + write + companion isolation); auto-skipped without TEST_USER_A/B credentials; 🧑 create two Supabase test accounts + add to .env to run live._
- [ ] **P6.12 🧑 Deploy** (Railway backend + Supabase + Vercel/static frontend); set all secrets (human).
- [x] **P6.13 Update** `README.md` + `RESUME_STORY.md`; commit.
      _Architecture section updated with full persistence layer; status reflects 88 tests + P6 complete; RESUME_STORY.md adds 6 persistence engineering decisions._
