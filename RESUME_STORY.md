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
| Live + 4 adversarial classics (Negroni w/o gin, Sazerac w/o Peychaud's, Mai Tai w/ bourbon only, count=5 from 3 bottles) | **100% grounded** | Model **flags, doesn't fake** — substitutes or marks `missing`, never claims an unowned bottle. But see below: grounding ≠ makeable. |

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

## Open decisions / next steps

- [x] **Pantry boundary:** decided — honey/cinnamon stay as legitimate "grab these"
  flags (kept the metric honest). Fixed via system-prompt tightening, not by widening
  the allowlist. Also fixed the hot-water normalization bug in the scorer.
- [x] **Adversarial scenarios added** (Negroni/Sazerac/Mai Tai/count=5). Live grounding
  stayed 100% — the model flags rather than fakes. Also fixed a matcher false-positive
  (generic "bitters"/"vermouth"/etc. no longer carry a match alone).
- [ ] **Add a `makeable rate` metric — now top priority.** Deterministic, complements
  grounding: an open-ended recommendation must use ≥1 owned bottle (the Mai Tai gamed
  grounding by being all-`missing`). Grounding = honesty; makeable = usefulness.
- [ ] **Run the LLM judge live** (constraint adherence, occasion fit, plausibility,
  name accuracy — would catch "Boulevardier called a Negroni"). Built + unit-tested, never run live.
- [ ] Wrap the core in a minimal FastAPI + one-screen frontend, deploy (live URL).
- [ ] README with an architecture diagram + the two "why I decided X" writeups.
