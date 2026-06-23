"""LLM-as-judge for the subjective dimensions the deterministic grounding scorer
can't measure: did the drink respect the user's constraints, fit the occasion,
and is it a plausible recipe.

Kept separate from grounding on purpose — grounding is mechanical and cheap;
judging is an LLM call and a soft signal. The interview point is exactly this
split: verify what you can in code, judge only what you must.

Like the recommender, the judge is wired for a real client but exercised offline
in tests via a fake client (no API key yet).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from recommender.llm import LLMClient
from recommender.schemas import RecommendRequest, Suggestion

JUDGE_SYSTEM = """You are a meticulous cocktail judge. Given a drink suggestion and
the user's request, score it.

CONSTRAINTS: If any stated constraint is violated, constraints_respected must be false.
Sweet vermouth violates "nothing too sweet". A shaken drink violates "stirred only".

NAME ACCURACY: A classic name belongs to a specific recipe. Set name_accurate to false if:
- The base spirit differs from the canonical recipe (bourbon instead of gin = not a Negroni;
  mezcal instead of tequila = not a Margarita). "Mezcal Negroni" is still false — it borrows
  the Negroni name for a different base spirit.
- A canonical ingredient is missing entirely (Old Fashioned without bitters = false;
  Sazerac without absinthe AND Peychaud's = false).
- The name claims it is a classic ("Negroni", "Manhattan", "Old Fashioned") but the recipe
  does not match. Descriptive names like "Boulevardier", "Bourbon Smash", "Rye Sour" are
  invented names — set name_accurate to true for those.

RECIPE PLAUSIBILITY (1-5): Is this a real, correctly-constructed cocktail?
- 5 = canonical technique, correct proportions, all expected components present
- 3 = mostly right but missing a key component or has odd ratios
- 1 = wouldn't work as written

If companions are listed, score companion_targeting 1-5: does the suited_for list
correctly match each companion's likes/dislikes? (5 = perfectly targeted, 1 = clearly
wrong). If no companions are present, omit companion_targeting entirely.

Respond with ONLY this JSON, no prose:
{"constraints_respected": true|false, "occasion_fit": 1-5, "recipe_plausibility": 1-5, "name_accurate": true|false, "companion_targeting": 1-5 or omit, "notes": "one sentence"}"""


class JudgeError(Exception):
    pass


class JudgeVerdict(BaseModel):
    constraints_respected: bool
    occasion_fit: int = Field(ge=1, le=5)
    recipe_plausibility: int = Field(ge=1, le=5)
    name_accurate: bool | None = None  # None = judge omitted the field; excluded from name_accuracy_rate
    companion_targeting: int | None = Field(None, ge=1, le=5)  # None when no companions present
    notes: str = ""


def build_judge_prompt(suggestion: Suggestion, request: RecommendRequest) -> str:
    lines = [f"Occasion: {request.occasion}"]
    if request.mood:
        lines.append(f"Mood/vibe: {request.mood}")
    if request.constraints:
        lines.append("Constraints (must be respected): " + "; ".join(request.constraints))
    if request.companions:
        for c in request.companions:
            parts = []
            if c.likes:
                parts.append("likes: " + ", ".join(c.likes))
            if c.dislikes:
                parts.append("dislikes: " + ", ".join(c.dislikes))
            lines.append(f"Companion {c.name}: {'; '.join(parts) or 'no stated preferences'}")

    lines.append(f"\nSuggestion: {suggestion.name}")
    lines.append(f"Description: {suggestion.description}")
    lines.append("Ingredients: " + ", ".join(
        f"{i.name} ({i.quantity})" if i.quantity else i.name for i in suggestion.ingredients
    ))
    if suggestion.steps:
        lines.append("Method: " + " ".join(suggestion.steps))
    if suggestion.suited_for:
        lines.append("Suited for: " + ", ".join(suggestion.suited_for))
    return "\n".join(lines)


def judge_suggestion(
    suggestion: Suggestion, request: RecommendRequest, llm: LLMClient
) -> JudgeVerdict:
    prompt = build_judge_prompt(suggestion, request)
    raw = llm.generate(JUDGE_SYSTEM, prompt)
    try:
        return _parse_verdict(raw)
    except (json.JSONDecodeError, ValidationError):
        raw = llm.generate(
            JUDGE_SYSTEM, prompt + "\n\nYour previous reply was not valid JSON. Respond with ONLY the JSON object."
        )
        try:
            return _parse_verdict(raw)
        except (json.JSONDecodeError, ValidationError) as e:
            raise JudgeError(f"Judge did not return a valid verdict: {e}") from e


def _parse_verdict(raw: str) -> JudgeVerdict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return JudgeVerdict.model_validate(json.loads(raw))


@dataclass
class JudgeSummary:
    verdicts: list[JudgeVerdict]

    @property
    def n(self) -> int:
        return len(self.verdicts)

    @property
    def constraint_pass_rate(self) -> float:
        if not self.verdicts:
            return 0.0
        return sum(v.constraints_respected for v in self.verdicts) / self.n

    @property
    def avg_occasion_fit(self) -> float:
        if not self.verdicts:
            return 0.0
        return sum(v.occasion_fit for v in self.verdicts) / self.n

    @property
    def avg_recipe_plausibility(self) -> float:
        if not self.verdicts:
            return 0.0
        return sum(v.recipe_plausibility for v in self.verdicts) / self.n

    @property
    def name_accuracy_rate(self) -> float | None:
        """Fraction of verdicts where name_accurate is True. None if no verdict included the field."""
        assessed = [v for v in self.verdicts if v.name_accurate is not None]
        if not assessed:
            return None
        return sum(v.name_accurate for v in assessed) / len(assessed)

    @property
    def name_accuracy_n(self) -> int:
        return sum(1 for v in self.verdicts if v.name_accurate is not None)

    @property
    def avg_companion_targeting(self) -> float | None:
        """Average companion_targeting score; None if no verdicts include the dimension."""
        assessed = [v for v in self.verdicts if v.companion_targeting is not None]
        if not assessed:
            return None
        return sum(v.companion_targeting for v in assessed) / len(assessed)

    @property
    def companion_targeting_n(self) -> int:
        return sum(1 for v in self.verdicts if v.companion_targeting is not None)


def summarize(verdicts: list[JudgeVerdict]) -> JudgeSummary:
    return JudgeSummary(verdicts)
