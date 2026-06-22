"""Print the live model's actual suggestions for chosen scenarios.

A debugging tool for reading *what* the model recommended, not just whether it
was grounded — grounding rate alone can't tell a sensible drink from one that
trivially marks everything "missing".

    python -m evals.inspect negroni_no_gin sazerac_no_peychauds
    python -m evals.inspect            # all scenarios
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from evals.fixtures import SCENARIOS
from recommender.llm import AnthropicClient
from recommender.recommender import recommend


def main() -> None:
    load_dotenv()
    by_id = {s.id: s for s in SCENARIOS}
    ids = sys.argv[1:] or [s.id for s in SCENARIOS]
    for sid in ids:
        sc = by_id[sid]
        rec = recommend(sc.request, sc.inventory, AnthropicClient())
        owns = ", ".join(b.name for b in sc.inventory)
        print(f"\n### {sid}  (owns: {owns})")
        for s in rec.suggestions:
            print(f"  - {s.name}")
            for ing in s.ingredients:
                q = f" {ing.quantity}" if ing.quantity else ""
                print(f"      {ing.source.value:10}{ing.name}{q}")


if __name__ == "__main__":
    main()
