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

## Task 1 — Makeable-rate metric (deterministic)  ·  Status: in progress

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
- [ ] **1.6 Run live once**: `.venv/bin/python -m evals.run_evals --live`. Record grounding + makeable
      numbers in `RESUME_STORY.md` metrics table. Commit (see git note above).

## Task 2 — Run the LLM judge live  ·  Status: not started

Goal: produce the quality numbers grounding can't (built + unit-tested, never run live).

- [ ] **2.1 Sanity-read `evals/run_evals.py`** `--judge` branch — confirm it calls `judge_suggestion`
      per suggestion with a live `AnthropicClient` and prints the `JudgeSummary` line.
- [ ] **2.2 (Optional, recommended) add a `name_accurate` bool** to `JudgeVerdict` in `evals/judge.py`
      + one line in `JUDGE_SYSTEM` ("if the drink's name doesn't match its actual recipe, set false").
      Add a `JudgeSummary.name_accuracy_rate`. Add a unit test in `tests/test_judge.py`.
      **Verify:** `.venv/bin/python -m pytest -q` green. _(Catches "Boulevardier called a Negroni".)_
- [ ] **2.3 Run** `.venv/bin/python -m evals.run_evals --live --judge`. Capture constraint pass rate,
      occasion fit, plausibility (and name accuracy if 2.2 done).
- [ ] **2.4 Record** the judge numbers in `RESUME_STORY.md`; commit.

## Task 3 — Deploy a thin vertical slice (live URL)  ·  Status: not started

Goal: a clickable demo. Keep it minimal — no DB, no auth, hardcoded inventory for v1.

- [ ] **3.1 Add deps** to `requirements.txt`: `fastapi`, `uvicorn[standard]`. `pip install -r requirements.txt`.
- [ ] **3.2 Create `app/main.py`**: FastAPI app; `POST /recommend` accepts a `RecommendRequest`
      (import from `recommender.schemas`), builds an `AnthropicClient`, calls `recommender.recommender.recommend`
      with a hardcoded inventory imported from `evals.fixtures.INVENTORY`, returns the `Recommendation`.
      Add `GET /inventory` returning that fixture inventory. Add CORS allowing the frontend origin.
      Load `.env` at startup.
- [ ] **3.3 Verify locally:** `.venv/bin/uvicorn app.main:app --reload`, then
      `curl -X POST localhost:8000/recommend -H 'content-type: application/json' -d '{"occasion":"movie night","count":2}'`
      returns grounded JSON.
- [ ] **3.4 Create `app/static/index.html`**: one screen — occasion text input, mood input, count, a
      "Suggest" button that `fetch`es `POST /recommend` and renders cards (name, ingredients with source
      badges, steps, why). Vanilla JS, no build step.
- [ ] **3.5 Serve static** from FastAPI (`StaticFiles` mounted at `/`). Verify the page works against local API.
- [ ] **3.6 🧑 Deploy to Railway**: a model can write `railway.toml` (start cmd
      `uvicorn app.main:app --host 0.0.0.0 --port $PORT`) and stage the deploy, but
      `railway login`, `railway up`, and setting `ANTHROPIC_API_KEY` in the dashboard
      are human steps (interactive auth + secrets). Hand off here.
- [ ] **3.7 🧑 Verify the live URL** end-to-end from a browser (human). Then put the URL in
      `README.md` and `RESUME_STORY.md`. Commit.

## Task 4 — README that tells the story  ·  Status: basic README + docs/eval-spec.md written; remaining = security writeup, fuller diagram + metrics table, demo link

- [x] **4.1 Overview section**: one paragraph — what it is, who it's for, the eval-first angle. _(done in README.md)_
- [x] **4.2 Architecture diagram**: ASCII diagram in README. _(upgrade to mermaid optional)_
- [~] **4.3 "Eval design" writeup**: summarized in README, fully specified in `docs/eval-spec.md`.
      Remaining: inline the metrics-timeline table from `RESUME_STORY.md` into the README.
- [ ] **4.4 "Security decision" writeup**: RLS-at-the-DB vs app-enforced `WHERE user_id`; why asyncpg would
      silently bypass RLS. _(Read `docs/adr-001-data-isolation.md` and summarize it — do not invent the rationale.)_
- [x] **4.5 Setup/run section**: venv, install, pytest, run_evals (mock + live). _(done in README; add "run the app" after Task 3)_
- [ ] **4.6 Live demo link** + a screenshot. Commit.

## Task 5 — CI gate on the evals  ·  Status: not started

- [ ] **5.1 Create `.github/workflows/ci.yml`**: trigger on push/PR; Python 3.14; `pip install -r requirements.txt`.
- [ ] **5.2 Run `pytest -q`** as a required step.
- [ ] **5.3 Run `python -m evals.run_evals`** (mock mode — no API key in CI). The runner already prints
      `PROPERTY FAILURES` and exits 0; **add a `--strict` flag** to `run_evals.py` that exits non-zero if any
      property assertion fails, and use it in CI so a regression fails the build.
- [ ] **5.4 🧑 (Optional) nightly live eval**: a model can write the workflow YAML, but adding the
      `ANTHROPIC_API_KEY` **repo secret** is a human step in GitHub settings. `schedule:` cron, runs
      `--live`; never on PRs (keeps tokens/secrets off forks).
- [ ] **5.5 Add a CI status badge** to `README.md`. Commit.

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

### P1 — Multi-model sweep  ·  Status: not started
Goal: benchmark Haiku/Sonnet/Opus on the eval and choose one, with cost/latency in the picture.
- [ ] **P1.1 Parameterize the model.** In `recommender/llm.py`, add a `model` arg to `AnthropicClient.__init__`
      (default the current Haiku id). In `evals/run_evals.py` add `--model <id>` and pass it through.
      **Verify:** `--live --model claude-haiku-4-5` still runs.
- [ ] **P1.2 Capture usage.** Have `AnthropicClient` record `input_tokens`/`output_tokens` per call
      (read `msg.usage`) onto a public counter on the instance. Add a price table
      `{model: (in_per_mtok, out_per_mtok)}` in `evals/sweep.py` (Haiku 1/5, Sonnet 4.6 3/15, Opus 4.8 5/25).
- [ ] **P1.3 Create `evals/sweep.py`.** For each model in a list, run all scenarios (grounding + makeable +
      judge), accumulate tokens + wall-clock, print one row per model: grounding%, makeable%, judge avgs,
      total tokens, est cost, total seconds.
- [ ] **P1.4 🧑 Run the sweep live** (3× token cost across 3 models — still cents). `.venv/bin/python -m evals.sweep`.
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

### P4 — Structured outputs via the API  ·  Status: not started
Goal: replace "ask for JSON + parse + retry" with schema-guaranteed output (Haiku 4.5 supports it).
- [ ] **P4.1 Read the structured-outputs section** of the `claude-api` skill (`output_config.format` /
      `messages.parse`); confirm the exact Python call shape before coding.
- [ ] **P4.2 Generate the schema** from the `Recommendation` pydantic model (`model_json_schema()`); strip
      unsupported constraints (min/max, etc.) per the skill's limitations list.
- [ ] **P4.3 Add a structured path** to `AnthropicClient` (e.g. `generate_structured(...)`) using
      `messages.parse(..., output_format=Recommendation)` or `output_config={"format": {...}}`.
- [ ] **P4.4 Switch `recommender.recommend`** to the structured path; keep the JSON-fence parse only as a fallback.
- [ ] **P4.5 Track parse-failure rate** before/after (should drop to ~0). Add a unit test that the structured
      path returns a valid `Recommendation`. **Verify:** `pytest -q` green; `--live` grounding/makeable unchanged.
- [ ] **P4.6 Record** "moved to schema-guaranteed output, parse failures → 0" in `RESUME_STORY`; commit.

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
- [ ] **P6.0 Write `docs/backend-spec.md`** — the authoritative backend spec. Must cover: data model
      (inventory, companions, sessions, session_drinks), endpoint surface, and explicitly resolve each of these
      known pitfalls: the **error-body contract** (match FastAPI's `{detail}` or add handlers), **pagination**
      (`limit`/`offset` everywhere or nowhere — pick one), a **unique key** for upsert/dedup (e.g. `UNIQUE(user_id, name)`),
      the **companion-feedback verdict→like/dislike rule**, and a concrete definition of **"current session"**.
- [ ] **P6.1 🧑 Create the Supabase project**; collect URL, anon key, service key, JWT secret (human).
- [ ] **P6.2 Write `backend/migrations/001_init.sql`** from the spec: tables + `UNIQUE(user_id, name)` where
      needed + RLS policies (`auth.uid() = user_id`) + `updated_at` trigger.
- [ ] **P6.3 🧑 Apply the migration** in the Supabase SQL editor (human).
- [ ] **P6.4 Auth dependency:** FastAPI `get_current_user` that verifies the Supabase JWT locally against the
      JWT secret and returns `user_id`; 401 on invalid. Unit-test with a signed test token.
- [ ] **P6.5 Data layer via `supabase-py` carrying the user JWT** (NOT asyncpg — per ADR). One thin module.
- [ ] **P6.6 Inventory endpoints** (GET/POST/PUT/DELETE, soft-delete via `is_active`). Tests: auth required, 404/403.
- [ ] **P6.7 Companions endpoints** + feedback (implement the verdict→like/dislike rule from the spec). Tests.
- [ ] **P6.8 Sessions + session_drinks endpoints**; implement "current session" per the spec. Tests.
- [ ] **P6.9 Point `/recommend` at the user's real inventory** (replace the hardcoded fixture from Task 3).
- [ ] **P6.10 Frontend:** login, inventory manage, companions, sessions, recommend screen (extend Task 3's page).
- [ ] **P6.11 RLS isolation test:** two users; confirm user A cannot read/write user B's rows.
- [ ] **P6.12 🧑 Deploy** (Railway backend + Supabase + Vercel/static frontend); set all secrets (human).
- [ ] **P6.13 Update** `README.md` + `RESUME_STORY.md`; commit.
