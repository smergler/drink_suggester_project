"""Tests for the makeable-rate metric."""

from __future__ import annotations

from evals.makeable import MakeableReport, is_makeable, is_makeable_now, score
from recommender.schemas import Bottle, Ingredient, IngredientSource, Suggestion

BOURBON = Bottle(id="1", name="Four Roses Bourbon", category="bourbon")
CAMPARI = Bottle(id="2", name="Campari", category="liqueur", subcategory="amaro")
INVENTORY = [BOURBON, CAMPARI]


def _suggestion(name: str, ingredients: list[Ingredient]) -> Suggestion:
    return Suggestion(name=name, description="", ingredients=ingredients)


def test_all_missing_not_makeable():
    """All-missing Mai-Tai-shaped suggestion → not makeable."""
    s = _suggestion("Mai Tai", [
        Ingredient(name="rum", source=IngredientSource.missing),
        Ingredient(name="orgeat", source=IngredientSource.missing),
        Ingredient(name="curacao", source=IngredientSource.missing),
    ])
    assert not is_makeable(s, INVENTORY)
    assert not is_makeable_now(s, INVENTORY)


def test_all_inventory_makeable_now():
    """All-inventory Boulevardier-shaped suggestion → makeable_now."""
    s = _suggestion("Boulevardier", [
        Ingredient(name="Four Roses Bourbon", source=IngredientSource.inventory),
        Ingredient(name="Campari", source=IngredientSource.inventory),
    ])
    assert is_makeable(s, INVENTORY)
    assert is_makeable_now(s, INVENTORY)


def test_one_owned_one_missing_uses_inventory_not_makeable_now():
    """1 owned + 1 missing → uses_inventory True, makeable_now False."""
    s = _suggestion("Almost Negroni", [
        Ingredient(name="Campari", source=IngredientSource.inventory),
        Ingredient(name="gin", source=IngredientSource.missing),
    ])
    assert is_makeable(s, INVENTORY)
    assert not is_makeable_now(s, INVENTORY)


def test_hallucinated_inventory_not_makeable_now():
    """Model claims inventory for a bottle not owned → uses_inventory True but makeable_now False."""
    s = _suggestion("Margarita", [
        Ingredient(name="Campari", source=IngredientSource.inventory),   # owned
        Ingredient(name="Tequila Blanco", source=IngredientSource.inventory),  # NOT owned, hallucinated
    ])
    assert is_makeable(s, INVENTORY)       # Campari is owned → True
    assert not is_makeable_now(s, INVENTORY)  # Tequila Blanco not in inventory → False


def test_score_aggregates():
    """score() returns correct counts across multiple suggestions."""
    all_missing = _suggestion("Mai Tai", [
        Ingredient(name="rum", source=IngredientSource.missing),
    ])
    makeable_now = _suggestion("Boulevardier", [
        Ingredient(name="Four Roses Bourbon", source=IngredientSource.inventory),
    ])
    partial = _suggestion("Almost Negroni", [
        Ingredient(name="Campari", source=IngredientSource.inventory),
        Ingredient(name="gin", source=IngredientSource.missing),
    ])
    report = score([all_missing, makeable_now, partial], INVENTORY)
    assert report.total == 3
    assert report.uses_inventory_count == 2  # makeable_now + partial
    assert report.makeable_now_count == 1    # only makeable_now
    assert abs(report.uses_inventory_rate - 2 / 3) < 1e-9
    assert abs(report.makeable_now_rate - 1 / 3) < 1e-9
