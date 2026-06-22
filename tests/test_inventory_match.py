from recommender.inventory_match import match_bottle
from recommender.schemas import Bottle

INV = [
    Bottle(id="1", name="Four Roses Small Batch", category="bourbon"),
    Bottle(id="2", name="Rittenhouse Rye", category="rye"),
    Bottle(id="4", name="Campari", category="liqueur"),
    Bottle(id="5", name="Carpano Antica Sweet Vermouth", category="vermouth"),
    Bottle(id="6", name="Dolin Dry Vermouth", category="vermouth"),
]


def _name(b):
    return b.name if b else None


def test_exact_and_partial_matches():
    assert _name(match_bottle("Four Roses Small Batch", INV)) == "Four Roses Small Batch"
    # stopwords (small, batch) dropped, still matches on four/roses
    assert _name(match_bottle("Four Roses", INV)) == "Four Roses Small Batch"
    assert _name(match_bottle("Rittenhouse", INV)) == "Rittenhouse Rye"
    assert _name(match_bottle("Campari", INV)) == "Campari"


def test_generic_name_matches_owned_specific_bottle():
    # user owns Carpano Antica; a recipe calling for "sweet vermouth" is grounded
    assert _name(match_bottle("sweet vermouth", INV)) == "Carpano Antica Sweet Vermouth"
    assert _name(match_bottle("dry vermouth", INV)) == "Dolin Dry Vermouth"


def test_unowned_spirits_do_not_match():
    assert match_bottle("white rum", INV) is None
    assert match_bottle("Tequila Blanco", INV) is None
    assert match_bottle("Aperol", INV) is None


def test_generic_category_word_alone_does_not_match():
    # owning Angostura Bitters must NOT make Peychaud's Bitters look owned
    inv = INV + [Bottle(id="7", name="Angostura Bitters", category="bitters")]
    assert match_bottle("Peychaud's Bitters", inv) is None
    assert match_bottle("Angostura Bitters", inv).name == "Angostura Bitters"
    # but the qualifier still carries sweet/dry vermouth to the owned bottle
    assert match_bottle("sweet vermouth", inv).name == "Carpano Antica Sweet Vermouth"


def test_empty_and_stopword_only_names():
    assert match_bottle("", INV) is None
    assert match_bottle("the of and", INV) is None
