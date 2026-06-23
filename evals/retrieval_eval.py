"""Retrieval quality eval — measures recall@k for labeled query→recipe pairs.

    python -m evals.retrieval_eval

Each query has a set of expected recipe names. We measure whether the expected
recipe appears in the top-k results (recall@k). A miss means the embedding space
doesn't associate the query style with that canonical recipe.
"""

from __future__ import annotations

from retrieval.search import search

# (query, {expected recipe names that should appear in top-k})
LABELED_QUERIES: list[tuple[str, set[str]]] = [
    ("classic gin aperitivo bitter", {"Negroni"}),
    ("bourbon rye Manhattan whiskey stirred", {"Manhattan"}),
    ("tequila lime citrus margarita", {"Margarita"}),
    ("rum tropical tiki lime orgeat", {"Mai Tai"}),
    ("gin lemon sour egg white", {"Tom Collins", "Gin Fizz"}),
    ("whiskey sour lemon citrus", {"Whiskey Sour"}),
    ("sparkling wine champagne prosecco", {"Kir Royale", "Bellini", "Mimosa"}),
    ("vodka lime ginger Moscow mule", {"Moscow Mule"}),
    ("rum mint lime mojito", {"Mojito"}),
    ("bourbon orange bitters classic old fashioned", {"Old Fashioned"}),
]

K = 10


def main() -> None:
    hits = 0
    total = len(LABELED_QUERIES)

    print(f"Retrieval eval — recall@{K}\n")
    print(f"{'query':<45} {'expected':<25} {'hit?'}")
    print("-" * 80)

    for query, expected in LABELED_QUERIES:
        results = search(query, k=K)
        result_names = {r.name for r in results}
        hit = bool(expected & result_names)
        hits += hit
        found = (expected & result_names) or {"—"}
        print(f"{query[:44]:<45} {', '.join(sorted(expected)):<25} {'✓' if hit else '✗'}  {', '.join(sorted(found)) if hit else ''}")

    print("-" * 80)
    print(f"Recall@{K}: {hits}/{total} = {hits/total:.0%}")


if __name__ == "__main__":
    main()
