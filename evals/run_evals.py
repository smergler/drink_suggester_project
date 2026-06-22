"""Run every scenario through the recommender and report grounding rate.

    python -m evals.run_evals            # offline, mock responses, zero tokens
    python -m evals.run_evals --live     # call the real Claude model
    python -m evals.run_evals --live --judge   # also run the LLM-as-judge

Live mode reads ANTHROPIC_API_KEY from the environment or a .env file.
"""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from evals.fixtures import SCENARIOS
from evals.grounding import score
from evals.judge import judge_suggestion, summarize
import evals.makeable as makeable_mod
from evals.mock_responses import MOCK_RESPONSES
from recommender.llm import AnthropicClient, MockClient
from recommender.recommender import recommend


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the recommendation eval.")
    parser.add_argument("--live", action="store_true", help="call the real Claude model")
    parser.add_argument("--judge", action="store_true", help="also run the LLM-as-judge (live only)")
    args = parser.parse_args()

    if args.live:
        load_dotenv()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit(
                "ANTHROPIC_API_KEY not set. Add it to a .env file at the project root "
                "or export it before running --live."
            )
        mode = "LIVE (claude-haiku-4-5-20251001)"
    else:
        mode = "MOCK (offline)"

    total = 0
    grounded = 0
    mk_total = 0
    mk_uses_inv = 0
    mk_now = 0
    property_failures: list[str] = []
    all_verdicts = []

    print(f"Mode: {mode}\n")
    header = f"{'scenario':<22}{'sugg':>5}{'grounded':>10}   violations"
    print(header)
    print("-" * max(len(header), 70))

    for sc in SCENARIOS:
        if args.live:
            llm = AnthropicClient()  # reads ANTHROPIC_API_KEY
        else:
            llm = MockClient(MOCK_RESPONSES, key=sc.id)

        rec = recommend(sc.request, sc.inventory, llm)
        report = score(rec.suggestions, sc.inventory)
        total += report.total
        grounded += report.grounded

        viol = [
            f"{c.name}: {v.name}({v.claimed.value})"
            for c in report.suggestion_checks
            for v in c.violations
        ]
        viol_str = "; ".join(viol) if viol else "—"
        print(f"{sc.id:<22}{report.total:>5}{report.grounded:>7}/{report.total:<2}   {viol_str}")

        if sc.expect_count is not None and report.total != sc.expect_count:
            property_failures.append(
                f"{sc.id}: expected {sc.expect_count} suggestions, got {report.total}"
            )
        if sc.expect_min_grounded_rate is not None and report.rate < sc.expect_min_grounded_rate:
            property_failures.append(
                f"{sc.id}: grounding {report.rate:.0%} < expected {sc.expect_min_grounded_rate:.0%}"
            )

        if sc.open_ended:
            mk = makeable_mod.score(rec.suggestions, sc.inventory)
            mk_total += mk.total
            mk_uses_inv += mk.uses_inventory_count
            mk_now += mk.makeable_now_count

        if args.live and args.judge:
            for s in rec.suggestions:
                all_verdicts.append(judge_suggestion(s, sc.request, llm))

    rate = grounded / total if total else 0.0
    mk_uses_rate = mk_uses_inv / mk_total if mk_total else 0.0
    mk_now_rate = mk_now / mk_total if mk_total else 0.0
    print("-" * max(len(header), 70))
    print(f"GROUNDING RATE:    {grounded}/{total} = {rate:.0%}")
    print(f"MAKEABLE RATE:     {mk_uses_inv}/{mk_total} = {mk_uses_rate:.0%}  (open-ended suggestions)")
    print(f"MAKEABLE-NOW RATE: {mk_now}/{mk_total} = {mk_now_rate:.0%}  (open-ended suggestions)")

    if all_verdicts:
        js = summarize(all_verdicts)
        print(
            f"JUDGE ({js.n} suggestions): "
            f"constraints respected {js.constraint_pass_rate:.0%}, "
            f"occasion fit {js.avg_occasion_fit:.1f}/5, "
            f"recipe plausibility {js.avg_recipe_plausibility:.1f}/5"
        )

    if property_failures:
        print(f"\nPROPERTY FAILURES ({len(property_failures)}):")
        for f in property_failures:
            print(f"  ✗ {f}")
    else:
        print("\nAll property assertions passed.")


if __name__ == "__main__":
    main()
