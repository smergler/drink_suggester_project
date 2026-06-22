from recommender.pantry import is_pantry, is_perishable, normalize


def test_normalize_lowercases_and_collapses_whitespace():
    assert normalize("  Four   Roses ") == "four roses"
    assert normalize("Ang.ostura") == "angostura"


def test_pantry_staples():
    assert is_pantry("ice")
    assert is_pantry("Simple Syrup")
    assert is_pantry("  SALT ")
    assert not is_pantry("Campari")
    assert not is_pantry("agave syrup")  # deliberately not a staple


def test_perishable_exact_and_substring():
    assert is_perishable("lime")
    assert is_perishable("fresh lime juice")   # substring tolerance
    assert is_perishable("orange peel")
    assert is_perishable("egg white")
    assert not is_perishable("Campari")
    assert not is_perishable("Four Roses Small Batch")
