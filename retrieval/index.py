"""Embed the cocktail corpus and cache vectors to disk.

Stack choice: local sentence-transformers (all-MiniLM-L6-v2) + numpy cosine.
No extra API key; runs fully offline after first model download (~80MB).
Voyage AI embeddings would be marginally better quality but add a dependency
and a key; local is the right call for a portfolio project.

    python -m retrieval.index            # embed + cache
    python -m retrieval.index --force    # re-embed even if cache exists
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

CORPUS_PATH = Path("data/cocktails.json")
VECTORS_PATH = Path("data/cocktails.vectors.npy")
MODEL_NAME = "all-MiniLM-L6-v2"


def _recipe_text(cocktail: dict) -> str:
    """Single string representation used for embedding — name + ingredients."""
    ingredients = ", ".join(i["name"] for i in cocktail["ingredients"])
    parts = [cocktail["name"]]
    if cocktail.get("category"):
        parts.append(cocktail["category"])
    parts.append(f"ingredients: {ingredients}")
    if cocktail.get("instructions"):
        parts.append(cocktail["instructions"][:200])
    return ". ".join(parts)


def build(force: bool = False) -> None:
    if VECTORS_PATH.exists() and not force:
        print(f"Cache hit: {VECTORS_PATH} already exists. Pass --force to re-embed.")
        return

    from sentence_transformers import SentenceTransformer

    corpus = json.loads(CORPUS_PATH.read_text())
    texts = [_recipe_text(c) for c in corpus]

    print(f"Embedding {len(texts)} cocktails with {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    vectors = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    np.save(VECTORS_PATH, vectors)
    print(f"Saved {vectors.shape} vectors to {VECTORS_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="re-embed even if cache exists")
    args = parser.parse_args()
    build(force=args.force)


if __name__ == "__main__":
    main()
