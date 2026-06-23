"""Compare human labels against LLM judge verdicts to measure calibration.

    python -m evals.calibrate_judge

Loads evals/judge_labels.json and evals/judge_verdicts.json, matches on
suggestion_hash, and reports per-dimension agreement stats.

Boolean dimensions:  percent agreement
1-5 dimensions:      mean absolute error (MAE) + exact match rate
"""

from __future__ import annotations

import json
from pathlib import Path

LABELS_PATH = Path("evals/judge_labels.json")
VERDICTS_PATH = Path("evals/judge_verdicts_calibration.json")

BOOL_DIMS = ["constraints_respected", "name_accurate"]
SCALE_DIMS = ["occasion_fit", "recipe_plausibility", "companion_targeting"]


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def _pct(num: int, den: int) -> str:
    return f"{num/den:.0%} ({num}/{den})" if den else "n/a (no pairs)"


def main() -> None:
    labels = _load(LABELS_PATH)
    verdicts = _load(VERDICTS_PATH)

    verdict_by_hash = {v["suggestion_hash"]: v for v in verdicts}

    matched = 0
    orphaned = 0

    # (human, judge) pairs per dimension
    bool_pairs: dict[str, list[tuple[bool, bool]]] = {d: [] for d in BOOL_DIMS}
    scale_pairs: dict[str, list[tuple[int, int]]] = {d: [] for d in SCALE_DIMS}

    for label in labels:
        h = label["suggestion_hash"]
        verdict = verdict_by_hash.get(h)
        if verdict is None:
            orphaned += 1
            continue
        matched += 1

        for dim in BOOL_DIMS:
            lv, jv = label.get(dim), verdict.get(dim)
            if lv is not None and jv is not None:
                bool_pairs[dim].append((bool(lv), bool(jv)))

        for dim in SCALE_DIMS:
            lv, jv = label.get(dim), verdict.get(dim)
            if lv is not None and jv is not None:
                scale_pairs[dim].append((int(lv), int(jv)))

    print(f"Labels: {len(labels)}  |  Matched: {matched}  |  Orphaned: {orphaned}\n")

    print("Boolean dimensions (% agreement)")
    print("-" * 50)
    for dim in BOOL_DIMS:
        pairs = bool_pairs[dim]
        agree = sum(h == j for h, j in pairs)
        print(f"  {dim:<28} {_pct(agree, len(pairs))}")
        for h, j in pairs:
            if h != j:
                print(f"    human={h}  judge={j}")

    print()
    print("Scale dimensions (MAE  |  exact match %)")
    print("-" * 50)
    for dim in SCALE_DIMS:
        pairs = scale_pairs[dim]
        if not pairs:
            print(f"  {dim:<28} n/a (no pairs)")
            continue
        mae = sum(abs(h - j) for h, j in pairs) / len(pairs)
        exact = sum(h == j for h, j in pairs)
        print(f"  {dim:<28} MAE={mae:.2f}  exact={_pct(exact, len(pairs))}")
        for h, j in pairs:
            if h != j:
                print(f"    human={h}  judge={j}")


if __name__ == "__main__":
    main()
