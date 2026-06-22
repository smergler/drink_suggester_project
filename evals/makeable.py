"""Makeable-rate metric — complementary to grounding.

Definitions
-----------
uses_inventory  : suggestion has ≥1 ingredient with source == inventory that
                  fuzzy-matches an owned bottle (via match_bottle).
makeable_now    : uses_inventory AND zero missing ingredients.

These are computed only for open-ended scenarios (open_ended=True). Named-drink
scenarios (open_ended=False) intentionally produce missing ingredients when a
classic's key bottle isn't owned — that's honest, not a failure.
"""

from __future__ import annotations

from dataclasses import dataclass

from recommender.inventory_match import match_bottle
from recommender.schemas import Bottle, IngredientSource, Suggestion


def is_makeable(suggestion: Suggestion, inventory: list[Bottle]) -> bool:
    """True if the suggestion uses ≥1 owned bottle (uses_inventory)."""
    for ing in suggestion.ingredients:
        if ing.source == IngredientSource.inventory and match_bottle(ing.name, inventory):
            return True
    return False


def is_makeable_now(suggestion: Suggestion, inventory: list[Bottle]) -> bool:
    """True if uses_inventory AND every claimed ingredient is actually available.

    Checks both:
    - no missing-tagged ingredients (honest disclosure)
    - every inventory-claimed ingredient fuzzy-matches an owned bottle (catches hallucination)
    """
    if not is_makeable(suggestion, inventory):
        return False
    for ing in suggestion.ingredients:
        if ing.source == IngredientSource.missing:
            return False
        if ing.source == IngredientSource.inventory and not match_bottle(ing.name, inventory):
            return False
    return True


@dataclass
class MakeableReport:
    total: int
    uses_inventory_count: int
    makeable_now_count: int

    @property
    def uses_inventory_rate(self) -> float:
        return self.uses_inventory_count / self.total if self.total else 0.0

    @property
    def makeable_now_rate(self) -> float:
        return self.makeable_now_count / self.total if self.total else 0.0


def score(suggestions: list[Suggestion], inventory: list[Bottle]) -> MakeableReport:
    uses = sum(1 for s in suggestions if is_makeable(s, inventory))
    now = sum(1 for s in suggestions if is_makeable_now(s, inventory))
    return MakeableReport(total=len(suggestions), uses_inventory_count=uses, makeable_now_count=now)
