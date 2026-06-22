from evals.grounding import check_suggestion, score
from recommender.schemas import Bottle, Ingredient, IngredientSource, Suggestion

INV = [
    Bottle(id="1", name="Four Roses Small Batch", category="bourbon"),
    Bottle(id="4", name="Campari", category="liqueur"),
]


def ing(name, source):
    return Ingredient(name=name, quantity="1 oz", source=source)


def sugg(name, ingredients):
    return Suggestion(name=name, description="", ingredients=ingredients)


def test_owned_inventory_is_grounded():
    c = check_suggestion(sugg("X", [ing("Four Roses Small Batch", IngredientSource.inventory)]), INV)
    assert c.grounded
    assert c.violations == []


def test_hallucinated_ownership_flagged():
    c = check_suggestion(sugg("X", [ing("white rum", IngredientSource.inventory)]), INV)
    assert not c.grounded
    assert c.violations[0].name == "white rum"


def test_pantry_misclassification_flagged():
    c = check_suggestion(sugg("X", [ing("agave syrup", IngredientSource.pantry)]), INV)
    assert not c.grounded


def test_real_pantry_staple_ok():
    assert check_suggestion(sugg("X", [ing("ice", IngredientSource.pantry)]), INV).grounded


def test_perishable_and_missing_not_policed_but_listed():
    c = check_suggestion(
        sugg("X", [
            ing("lime", IngredientSource.perishable),
            ing("Aperol", IngredientSource.missing),
        ]),
        INV,
    )
    assert c.grounded
    assert "lime" in c.shopping_list
    assert "Aperol" in c.shopping_list


def test_rate_computation():
    good = sugg("good", [ing("Campari", IngredientSource.inventory)])
    bad = sugg("bad", [ing("white rum", IngredientSource.inventory)])
    report = score([good, bad], INV)
    assert report.total == 2
    assert report.grounded == 1
    assert report.rate == 0.5
