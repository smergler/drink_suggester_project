"""Free-form matching of an ingredient name to an owned bottle.

This fuzzy layer exists *because* we let the model name bottles freely. It is
exactly the code that ID-constraining the model would later make unnecessary —
the planned lever for pushing grounding rate up.
"""

from __future__ import annotations

from .pantry import normalize
from .schemas import Bottle


def _tokens(s: str) -> set[str]:
    return set(normalize(s).split())


# Tokens too generic to carry a match on their own. Generic category nouns are
# included so "Peychaud's Bitters" does NOT match an owned "Angostura Bitters"
# on the shared word "bitters" — the brand/qualifier token must overlap instead.
# (Subcategory words like bourbon/rye/mezcal are intentionally NOT here, so a
# recipe calling for generic "rye" still matches an owned "Rittenhouse Rye".)
_STOPWORDS = {
    "the", "of", "and", "small", "batch", "bottle",
    "bitters", "vermouth", "liqueur", "syrup",
    "rum", "gin", "vodka", "whiskey", "whisky", "tequila", "brandy", "cognac",
}


def match_bottle(ingredient_name: str, inventory: list[Bottle]) -> Bottle | None:
    ing = _tokens(ingredient_name) - _STOPWORDS
    if not ing:
        return None
    best: tuple[float, Bottle] | None = None
    for b in inventory:
        bt = _tokens(b.name) - _STOPWORDS
        if not bt:
            continue
        overlap = ing & bt
        if not overlap:
            continue
        # fraction of the smaller token set that overlaps
        score = len(overlap) / min(len(ing), len(bt))
        if score >= 0.5 and (best is None or score > best[0]):
            best = (score, b)
    return best[1] if best else None
