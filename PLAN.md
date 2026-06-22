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

## Task 1 — Makeable-rate metric (deterministic)  ·  Status: not started

Goal: a metric that complements grounding. Grounding = "honest about ownership";
makeable = "actually buildable from owned bottles." Closes the all-`missing` Mai Tai gap.

- [ ] **1.1 Decide + document the definition** in a comment at the top of the new file:
      `uses_inventory` = suggestion has ≥1 ingredient with `source == inventory` that matches an owned bottle;
      `makeable_now` = `uses_inventory` AND zero `missing` ingredients.
- [ ] **1.2 Add `open_ended: bool = True` field** to the `Scenario` dataclass in `evals/fixtures.py`.
      Set `open_ended=False` on the four named-drink scenarios (negroni_no_gin, sazerac_no_peychauds,
      mai_tai_bourbon_only) — a user who *demands* a specific classic accepts a shopping list.
      Leave `high_count_pad` and all occasion/mood scenarios `open_ended=True`.
- [ ] **1.3 Create `evals/makeable.py`** with: `is_makeable(suggestion, inventory) -> bool` (uses_inventory),
      `is_makeable_now(suggestion, inventory) -> bool`, and `score(suggestions, inventory) -> MakeableReport`
      (dataclass with `.uses_inventory_rate` and `.makeable_now_rate`). Reuse `recommender.inventory_match.match_bottle`.
- [ ] **1.4 Create `tests/test_makeable.py`**: all-`missing` Mai-Tai-shaped suggestion → not makeable;
      all-`inventory` Boulevardier-shaped → makeable_now; 1 owned + 1 missing → uses_inventory True, makeable_now False.
      **Verify:** `.venv/bin/python -m pytest -q` all green.
- [ ] **1.5 Wire into `evals/run_evals.py`**: compute makeable over `open_ended` scenarios only;
      print `MAKEABLE RATE` and `MAKEABLE-NOW RATE` lines under `GROUNDING RATE`.
      **Verify:** `.venv/bin/python -m evals.run_evals` prints both, no crash.
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

## Task 4 — README that tells the story  ·  Status: not started

- [ ] **4.1 Overview section**: one paragraph — what it is, who it's for, the eval-first angle.
- [ ] **4.2 Architecture diagram** (mermaid or ASCII): request → pre-filter/context → Claude (structured) → parse → eval.
- [ ] **4.3 "Eval design" writeup**: the triad — deterministic grounding + makeable (set math) and LLM judge
      (subjective); why the split. Pull the metrics-timeline table from `RESUME_STORY.md`.
- [ ] **4.4 "Security decision" writeup**: RLS-at-the-DB vs app-enforced `WHERE user_id`; why asyncpg would
      silently bypass RLS. _(Read `docs/adr-001-data-isolation.md` and summarize it — do not invent the rationale.)_
- [ ] **4.5 Setup/run section**: venv, `pip install -r requirements.txt`, pytest, run_evals (mock + live), run the app.
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

## Phase 2 — after the 5 (not yet broken into subtasks)

Ordered by AI/ML-resume signal. Break each into subtasks before starting it.

- [ ] **P1 · Multi-model sweep.** Run the eval across Haiku / Sonnet / Opus; compare grounding,
      makeable, judge scores **and** cost/latency. Deliverable: a results table + a "why I chose X" note.
      _(Highest signal-per-hour: "I benchmarked 3 models on my own eval and chose X.")_
- [ ] **P2 · Judge calibration.** Hand-label ~15 outputs; measure whether the LLM judge agrees.
      Shows you don't blindly trust an LLM judge. Deliverable: agreement rate + disagreement notes.
- [ ] **P3 · Retrieval / RAG.** Embed a corpus of real cocktail recipes; retrieve similar drinks to
      ground/inspire suggestions beyond parametric memory. Add a retrieval-quality metric. _(Biggest capability jump.)_
- [ ] **P4 · Structured outputs via the API.** Replace "ask for JSON + parse + retry" with
      `output_config.format` (Haiku 4.5 supports it) for schema-guaranteed output. Reliability upgrade.
- [ ] **P5 · Observability / tracing.** Log every LLM call (tokens, latency, cost, grounding result) to a
      simple store; optional tiny dashboard. "I instrumented my LLM calls" = production-AI signal.
- [ ] **P6 · The real backend (breadth).** Auth + DB + RLS + persistence (inventory/companions/sessions).
      **This is where `docs/adr-001-data-isolation.md` and the prompt-review findings get used.** Turns the
      demo into a multi-user app. Before building, externalize the prompt-review findings (still only in chat).
