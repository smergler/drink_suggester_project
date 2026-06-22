"""Fixture inventory and test scenarios.

Eval is property-based: we don't assert exact model text, we assert properties
of the output (grounded, count, constraints respected).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from recommender.schemas import Bottle, CompanionProfile, RecommendRequest

INVENTORY = [
    Bottle(id="1", name="Four Roses Small Batch", category="bourbon"),
    Bottle(id="2", name="Rittenhouse Rye", category="rye"),
    Bottle(id="3", name="Del Maguey Vida Mezcal", category="mezcal", subcategory="joven"),
    Bottle(id="4", name="Campari", category="liqueur", subcategory="amaro"),
    Bottle(id="5", name="Carpano Antica Sweet Vermouth", category="vermouth", subcategory="sweet"),
    Bottle(id="6", name="Dolin Dry Vermouth", category="vermouth", subcategory="dry"),
    Bottle(id="7", name="Angostura Bitters", category="bitters"),
    Bottle(id="8", name="Cointreau", category="liqueur", subcategory="orange"),
]

SPARSE = INVENTORY[:1]   # bourbon only
SMALL = INVENTORY[:3]    # bourbon, rye, mezcal


@dataclass
class Scenario:
    id: str
    request: RecommendRequest
    inventory: list[Bottle]
    note: str = ""
    # property assertions (checked by the runner where set)
    expect_min_grounded_rate: float | None = None
    expect_count: int | None = None


SCENARIOS: list[Scenario] = [
    Scenario(
        id="classic_rich",
        inventory=INVENTORY,
        request=RecommendRequest(
            occasion="dinner party",
            mood="spirit-forward",
            count=2,
            available_perishables=["orange"],
        ),
        note="Rich inventory, easy ask — should be fully grounded.",
        expect_min_grounded_rate=1.0,
        expect_count=2,
    ),
    Scenario(
        id="negroni_no_sweet",
        inventory=INVENTORY,
        request=RecommendRequest(
            occasion="aperitivo",
            mood="bitter and bracing",
            count=1,
            constraints=["nothing too sweet", "stirred only"],
        ),
        note="Constraint-heavy; tests adherence + grounding.",
        expect_min_grounded_rate=1.0,
    ),
    Scenario(
        id="sparse_old_fashioned",
        inventory=SPARSE,
        request=RecommendRequest(
            occasion="nightcap",
            mood="simple and warming",
            count=1,
            available_perishables=["orange"],
        ),
        note="Bourbon only: bitters must be flagged missing, not faked.",
        expect_min_grounded_rate=1.0,
    ),
    Scenario(
        id="tiki_adversarial",
        inventory=SPARSE,
        request=RecommendRequest(
            occasion="tiki beach party",
            mood="tropical and fruity",
            count=1,
        ),
        note="Only bourbon, asked for tiki: honesty stress test. Mock hallucinates rum.",
    ),
    Scenario(
        id="impossible_count",
        inventory=SPARSE,
        request=RecommendRequest(
            occasion="casual evening",
            mood="surprise me",
            count=3,
        ),
        note="3 drinks from 1 bottle: does it pad with invented bottles?",
        expect_count=3,
    ),
    Scenario(
        id="companion_mezcal",
        inventory=INVENTORY,
        request=RecommendRequest(
            occasion="date night",
            mood="smoky",
            count=1,
            companions=[CompanionProfile(name="wife", likes=["mezcal", "spirit-forward"], dislikes=["sweet"])],
        ),
        note="Personalization; mock mislabels agave syrup as pantry.",
    ),
    Scenario(
        id="margarita_no_tequila",
        inventory=INVENTORY,
        request=RecommendRequest(
            occasion="taco night",
            mood="bright and citrusy",
            count=1,
            available_perishables=["lime"],
        ),
        note="No tequila owned; mock fakes it as inventory.",
    ),
    Scenario(
        id="movie_night",
        inventory=INVENTORY,
        request=RecommendRequest(
            occasion="movie night",
            mood="cozy",
            count=1,
            available_perishables=["lemon", "orange"],
        ),
        note="Normal case, should be grounded.",
        expect_min_grounded_rate=1.0,
    ),
    # --- adversarial: named classics whose key ingredients aren't owned ---
    # No property assertions — these are observational grounding probes.
    Scenario(
        id="negroni_no_gin",
        inventory=[INVENTORY[3], INVENTORY[4], INVENTORY[0]],  # Campari, sweet vermouth, bourbon — NO gin
        request=RecommendRequest(
            occasion="aperitivo", mood="classic and bitter", count=1,
            constraints=["make a Negroni"], available_perishables=["orange"],
        ),
        note="Negroni's base spirit (gin) isn't owned. Fake gin, substitute (Boulevardier), or flag missing?",
    ),
    Scenario(
        id="sazerac_no_peychauds",
        inventory=[INVENTORY[1], INVENTORY[6]],  # rye + Angostura — NO Peychaud's, NO absinthe
        request=RecommendRequest(
            occasion="nightcap", mood="classic", count=1, constraints=["make a Sazerac"],
        ),
        note="Sazerac needs Peychaud's + absinthe, neither owned. Does it fake the specialty items?",
    ),
    Scenario(
        id="mai_tai_bourbon_only",
        inventory=SPARSE,  # bourbon only
        request=RecommendRequest(
            occasion="beach party", mood="tropical", count=1, constraints=["make a Mai Tai"],
        ),
        note="Named tiki drink needing rum/orgeat/curacao/lime against bourbon-only. Lots to fake.",
    ),
    Scenario(
        id="high_count_pad",
        inventory=SMALL,  # bourbon, rye, mezcal
        request=RecommendRequest(occasion="casual evening", mood="surprise me", count=5),
        note="5 drinks from 3 bottles — does it invent bottles to hit the count?",
    ),
]
