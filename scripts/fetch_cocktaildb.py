"""Fetch all cocktails from TheCocktailDB free API and write data/cocktails.json.

    python -m scripts.fetch_cocktaildb

Hits the search-by-first-letter endpoint for a-z, normalizes the response,
and writes a clean corpus for RAG indexing.
"""

from __future__ import annotations

import json
import string
import time
from pathlib import Path

import httpx

OUTPUT = Path("data/cocktails.json")
BASE = "https://www.thecocktaildb.com/api/json/v1/1/search.php"


def _parse_ingredients(drink: dict) -> list[dict]:
    ingredients = []
    for i in range(1, 16):
        name = (drink.get(f"strIngredient{i}") or "").strip()
        measure = (drink.get(f"strMeasure{i}") or "").strip()
        if name:
            ingredients.append({"name": name, "measure": measure or None})
    return ingredients


def main() -> None:
    cocktails = []
    seen_ids: set[str] = set()

    for letter in string.ascii_lowercase:
        resp = httpx.get(BASE, params={"f": letter}, timeout=10)
        resp.raise_for_status()
        drinks = resp.json().get("drinks") or []
        for d in drinks:
            cid = d["idDrink"]
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            cocktails.append({
                "id": cid,
                "name": d["strDrink"],
                "category": d.get("strCategory") or None,
                "alcoholic": d.get("strAlcoholic") or None,
                "glass": d.get("strGlass") or None,
                "instructions": (d.get("strInstructions") or "").strip() or None,
                "ingredients": _parse_ingredients(d),
            })
        print(f"  {letter}: {len(drinks)} drinks  (total {len(cocktails)})")
        time.sleep(0.1)

    OUTPUT.write_text(json.dumps(cocktails, indent=2, ensure_ascii=False))
    print(f"\nWrote {len(cocktails)} cocktails to {OUTPUT}")


if __name__ == "__main__":
    main()
