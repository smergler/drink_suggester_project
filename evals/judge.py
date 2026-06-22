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
the user's request, score it. Be strict: if any stated constraint is violated,
constraints_respected must be false. If the drink has a recognized classic name but
its listed ingredients don't match that classic's canonical recipe (e.g. called a
'Negroni' but contains bourbon instead of gin), set name_accurate to false. If the
drink has an invented or creative name, set name_accurate to true unless the
description explicitly claims it is a classic it clearly is not.

Respond with ONLY this JSON, no prose:
{"constraints_respected": true|false, "occasion_fit": 1-5, "recipe_plausibility": 1-5, "name_accurate": true|false, "notes": "one sentence"}"""


class JudgeError(Exception):
    pass


class JudgeVerdict(BaseModel):
    constraints_respected: bool
    occasion_fit: int = Field(ge=1, le=5)
    recipe_plausibility: int = Field(ge=1, le=5)
    name_accurate: bool | None = None  # None = judge omitted the field; excluded from name_accuracy_rate
    notes: str = ""


def build_judge_prompt(suggestion: Suggestion, request: RecommendRequest) -> str:
    lines = [f"Occasion: {request.occasion}"]
    if request.mood:
        lines.append(f"Mood/vibe: {request.mood}")
    if request.constraints:
        lines.append("Constraints (must be respected): " + "; ".join(request.constraints))
    dislikes = [d for c in request.companions for d in c.dislikes]
    if dislikes:
        lines.append("Companion dislikes (avoid): " + ", ".join(sorted(set(dislikes))))

    lines.append(f"\nSuggestion: {suggestion.name}")
    lines.append(f"Description: {suggestion.description}")
    lines.append("Ingredients: " + ", ".join(
        f"{i.name} ({i.quantity})" if i.quantity else i.name for i in suggestion.ingredients
    ))
    if suggestion.steps:
        lines.append("Method: " + " ".join(suggestion.steps))
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


def summarize(verdicts: list[JudgeVerdict]) -> JudgeSummary:
    return JudgeSummary(verdicts)
