# Drink Suggester — Resume / Interview Story

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

| Milestone | Grounding rate | Notes |
|---|---|---|
| Mock baseline (offline, seeded-violation stubs) | **64%** | Proved the scorer catches hallucinated ownership before spending a token. |
| **Live baseline** (claude-haiku-4-5) | **91%** | 10/11 grounded. The 1 failure: model labeled honey/cinnamon as `pantry` (over-assumed on-hand). |
| After tightening the pantry definition in the system prompt | **100%** | Model now flags honey/spices as `perishable` ("grab these") instead of assuming them. Real before/after. |
| (next) add adversarial scenarios | _TBD, by design < 100%_ | 100% on easy cases is **not** a credible gate. Adding harder cases to give the metric teeth — a metric that always passes proves nothing. |

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

## Interview-ready sentences

- "I tracked *grounding rate* as my primary metric — the percent of recommendations
  where every ingredient is something the user actually owns or is explicitly told
  to buy. It's deterministic, so it's defensible."
- "I split evaluation into deterministic checks for what I could verify mechanically
  and an LLM judge for the subjective parts."
- "I built and measured against mocks first, with seeded failures, so I knew the
  harness worked before spending a token."
- "The eval caught the model over-assuming pantry items; I tightened the grounding
  definition and the rate moved from X to Y."

## Open decisions / next steps

- [x] **Pantry boundary:** decided — honey/cinnamon stay as legitimate "grab these"
  flags (kept the metric honest). Fixed via system-prompt tightening, not by widening
  the allowlist. Also fixed the hot-water normalization bug in the scorer.
- [ ] **Add adversarial scenarios the live model actually trips on — now top priority.**
  Live grounding hit 100% on the current set, which means the eval is too easy to be a
  credible quality gate. Need cases targeting known LLM grounding failure modes (e.g.
  asking for a named classic whose base spirit the user doesn't own, to see if the
  model fakes it as `inventory` vs. substitutes vs. flags `missing`).
- [ ] Wrap the core in a minimal FastAPI + one-screen frontend, deploy (live URL).
- [ ] README with an architecture diagram + the two "why I decided X" writeups.
