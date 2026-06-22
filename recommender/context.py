from __future__ import annotations

from .schemas import Bottle, RecommendRequest

SYSTEM_PROMPT = """You are a skilled bartender with deep cocktail knowledge.
You recommend drinks the user can actually make from the bottles they own.

For EVERY ingredient you must label its "source":
- "inventory": a bottle from the user's list below. Use this only if the bottle
  is genuinely on the list.
- "pantry": ONLY one of these always-stocked staples — ice, water, sugar, simple
  syrup, demerara syrup, salt. Nothing else qualifies as pantry.
- "perishable": any non-bottle ingredient that varies household to household —
  citrus, juices, egg, herbs, honey, spices (e.g. cinnamon), cream, garnishes.
  Use this for anything edible that is NOT a bottle and is NOT a pantry staple.
- "missing": a specialty bottle/liqueur/bitters/vermouth/syrup the user does NOT own.

Never label something "inventory" or "pantry" unless it truly belongs there.
Do NOT label honey, spices, juices, dairy, or specialty syrups as "pantry" — they
go under "perishable" so the user is told to grab them. If a great drink needs a
bottle the user lacks, include it as "missing" rather than pretending they have it.

Respond with ONLY a JSON object of this shape, no prose:
{"suggestions":[{"name": "...","description":"...","ingredients":[{"name":"...","quantity":"...","source":"inventory|pantry|perishable|missing"}],"steps":["..."],"why":"..."}]}"""


def build_context(req: RecommendRequest, inventory: list[Bottle]) -> str:
    lines: list[str] = [f"Occasion: {req.occasion}"]
    if req.mood:
        lines.append(f"Mood/vibe: {req.mood}")
    lines.append(f"Number of suggestions wanted: {req.count}")

    lines.append("\nBottles the user owns:")
    for b in inventory:
        sub = f" / {b.subcategory}" if b.subcategory else ""
        lines.append(f"- {b.name} [{b.category}{sub}]")

    if req.available_perishables:
        lines.append(
            "\nFresh ingredients on hand: " + ", ".join(req.available_perishables)
        )
    else:
        lines.append("\nFresh ingredients on hand: none confirmed")

    if req.companions:
        lines.append("\nDrinking companions:")
        for c in req.companions:
            likes = ", ".join(c.likes) or "—"
            dislikes = ", ".join(c.dislikes) or "—"
            lines.append(f"- {c.name}: likes {likes}; dislikes {dislikes}")

    if req.constraints:
        lines.append("\nConstraints: " + "; ".join(req.constraints))

    return "\n".join(lines)
