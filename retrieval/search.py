"""Semantic search over the cocktail corpus using cached embeddings.

    from retrieval.search import search
    results = search("smoky spirit-forward aperitivo with mezcal", k=5)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

CORPUS_PATH = Path("data/cocktails.json")
VECTORS_PATH = Path("data/cocktails.vectors.npy")
MODEL_NAME = "all-MiniLM-L6-v2"

_corpus: list[dict] | None = None
_vectors: np.ndarray | None = None
_model = None


@dataclass
class Recipe:
    id: str
    name: str
    category: str | None
    ingredients: list[dict]
    instructions: str | None
    score: float


def _load() -> None:
    global _corpus, _vectors, _model
    if _corpus is not None:
        return

    if not VECTORS_PATH.exists():
        raise FileNotFoundError(
            f"{VECTORS_PATH} not found — run `python -m retrieval.index` first."
        )

    from sentence_transformers import SentenceTransformer

    _corpus = json.loads(CORPUS_PATH.read_text())
    _vectors = np.load(VECTORS_PATH)
    _model = SentenceTransformer(MODEL_NAME)


def search(query: str, k: int = 5) -> list[Recipe]:
    """Return the k most semantically similar cocktails for query."""
    _load()

    query_vec = _model.encode([query], convert_to_numpy=True)[0]

    # cosine similarity: dot product of unit vectors
    norms = np.linalg.norm(_vectors, axis=1, keepdims=True)
    normed = _vectors / np.where(norms == 0, 1, norms)
    query_normed = query_vec / (np.linalg.norm(query_vec) or 1)
    scores = normed @ query_normed

    top_idx = np.argsort(scores)[::-1][:k]

    return [
        Recipe(
            id=_corpus[i]["id"],
            name=_corpus[i]["name"],
            category=_corpus[i].get("category"),
            ingredients=_corpus[i]["ingredients"],
            instructions=_corpus[i].get("instructions"),
            score=float(scores[i]),
        )
        for i in top_idx
    ]
