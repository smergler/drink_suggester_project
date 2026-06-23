"""Run every scenario through the recommender and report grounding rate.

    python -m evals.run_evals            # offline, mock responses, zero tokens
    python -m evals.run_evals --live     # call the real Claude model
    python -m evals.run_evals --live --judge   # also run the LLM-as-judge

Live mode reads ANTHROPIC_API_KEY from the environment or a .env file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from evals.fixtures import SCENARIOS
from evals.grounding import score
from evals.judge import JudgeVerdict, judge_suggestion, summarize
import evals.makeable as makeable_mod
from evals.mock_responses import MOCK_RESPONSES
from recommender.llm import AnthropicClient, MockClient
from recommender.recommender import recommend


def _suggestion_hash(suggestion) -> str:
    """Stable 8-char hash of sorted ingredient names+sources — recipe identity."""
    key = sorted(
        [{"name": i.name, "source": i.source.value} for i in suggestion.ingredients],
        key=lambda x: x["name"],
    )
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:8]


@dataclass
class TaggedVerdict:
    scenario_id: str
    suggestion_name: str
    suggestion_hash: str
    verdict: JudgeVerdict


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the recommendation eval.")
    parser.add_argument("--live", action="store_true", help="call the real Claude model")
    parser.add_argument("--judge", action="store_true", help="also run the LLM-as-judge (live only)")
    parser.add_argument("--strict", action="store_true", help="exit non-zero if any property assertion fails (for CI)")
    parser.add_argument("--model", default=None, help="override model id (live only; default: haiku)")
    parser.add_argument("--save-verdicts", metavar="PATH", help="write per-suggestion judge verdicts to JSON")
    parser.add_argument("--save-suggestions", metavar="PATH", help="write full suggestion details + scenario context to JSON")
    args = parser.parse_args()

    if args.live:
        load_dotenv()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit(
                "ANTHROPIC_API_KEY not set. Add it to a .env file at the project root "
                "or export it before running --live."
            )
        _probe = AnthropicClient(model=args.model)
        mode = f"LIVE ({_probe._model})"
    else:
        mode = "MOCK (offline)"

    total = 0
    grounded = 0
    mk_total = 0
    mk_uses_inv = 0
    mk_now = 0
    property_failures: list[str] = []
    all_tagged: list[TaggedVerdict] = []
    all_suggestions: list[dict] = []

    print(f"Mode: {mode}\n")
    header = f"{'scenario':<22}{'sugg':>5}{'grounded':>10}   violations"
    print(header)
    print("-" * max(len(header), 70))

    for sc in SCENARIOS:
        if args.live:
            llm = AnthropicClient(model=args.model)  # reads ANTHROPIC_API_KEY
        else:
            llm = MockClient(MOCK_RESPONSES, key=sc.id)

        rec = recommend(sc.request, sc.inventory, llm)
        report = score(rec.suggestions, sc.inventory)

        if args.save_suggestions:
            companions = [
                {"name": c.name, "likes": c.likes, "dislikes": c.dislikes}
                for c in sc.request.companions
            ]
            for s in rec.suggestions:
                all_suggestions.append({
                    "suggestion_hash": _suggestion_hash(s),
                    "scenario_id": sc.id,
                    "occasion": sc.request.occasion,
                    "mood": sc.request.mood,
                    "constraints": sc.request.constraints,
                    "companions": companions,
                    "name": s.name,
                    "description": s.description,
                    "ingredients": [
                        {"name": i.name, "quantity": i.quantity, "source": i.source.value}
                        for i in s.ingredients
                    ],
                    "steps": s.steps,
                    "why": s.why,
                    "suited_for": s.suited_for,
                })
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
        if sc.check_suited_for:
            valid_names = {"me"} | {c.name for c in sc.request.companions}
            for s in rec.suggestions:
                for name in s.suited_for:
                    if name not in valid_names:
                        property_failures.append(
                            f"{sc.id} '{s.name}': suited_for contains unknown name '{name}'"
                        )

        if sc.open_ended:
            mk = makeable_mod.score(rec.suggestions, sc.inventory)
            mk_total += mk.total
            mk_uses_inv += mk.uses_inventory_count
            mk_now += mk.makeable_now_count

        if args.live and args.judge:
            for s in rec.suggestions:
                verdict = judge_suggestion(s, sc.request, llm)
                all_tagged.append(TaggedVerdict(sc.id, s.name, _suggestion_hash(s), verdict))

    rate = grounded / total if total else 0.0
    mk_uses_rate = mk_uses_inv / mk_total if mk_total else 0.0
    mk_now_rate = mk_now / mk_total if mk_total else 0.0
    print("-" * max(len(header), 70))
    print(f"GROUNDING RATE:    {grounded}/{total} = {rate:.0%}")
    print(f"MAKEABLE RATE:     {mk_uses_inv}/{mk_total} = {mk_uses_rate:.0%}  (open-ended suggestions)")
    print(f"MAKEABLE-NOW RATE: {mk_now}/{mk_total} = {mk_now_rate:.0%}  (open-ended suggestions)")

    if all_tagged:
        all_verdicts = [t.verdict for t in all_tagged]
        js = summarize(all_verdicts)
        name_acc = (
            f"{js.name_accuracy_rate:.0%} ({js.name_accuracy_n}/{js.n})"
            if js.name_accuracy_rate is not None else "n/a"
        )
        comp_tgt = (
            f"{js.avg_companion_targeting:.1f}/5 ({js.companion_targeting_n} scored)"
            if js.avg_companion_targeting is not None else "n/a (no companion scenarios)"
        )
        print(
            f"JUDGE ({js.n} suggestions): "
            f"constraints respected {js.constraint_pass_rate:.0%}, "
            f"occasion fit {js.avg_occasion_fit:.1f}/5, "
            f"recipe plausibility {js.avg_recipe_plausibility:.1f}/5, "
            f"name accuracy {name_acc}, "
            f"companion targeting {comp_tgt}"
        )

    if all_tagged and args.save_verdicts:
        rows = [
            {
                "suggestion_hash": t.suggestion_hash,
                "scenario_id": t.scenario_id,
                "suggestion_name": t.suggestion_name,
                "constraints_respected": t.verdict.constraints_respected,
                "occasion_fit": t.verdict.occasion_fit,
                "recipe_plausibility": t.verdict.recipe_plausibility,
                "name_accurate": t.verdict.name_accurate,
                "companion_targeting": t.verdict.companion_targeting,
                "notes": t.verdict.notes,
            }
            for t in all_tagged
        ]
        Path(args.save_verdicts).write_text(json.dumps(rows, indent=2))
        print(f"\nVerdicts saved to {args.save_verdicts}")

    if all_suggestions and args.save_suggestions:
        Path(args.save_suggestions).write_text(json.dumps(all_suggestions, indent=2))
        print(f"Suggestions saved to {args.save_suggestions}")

    if property_failures:
        print(f"\nPROPERTY FAILURES ({len(property_failures)}):")
        for f in property_failures:
            print(f"  ✗ {f}")
        if args.strict:
            raise SystemExit(1)
    else:
        print("\nAll property assertions passed.")


if __name__ == "__main__":
    main()
