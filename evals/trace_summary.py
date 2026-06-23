"""Summarise a JSONL trace file produced by evals/tracing.py.

    python -m evals.trace_summary                     # default: evals/traces.jsonl
    python -m evals.trace_summary evals/traces.jsonl
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evals/traces.jsonl")
    if not path.exists():
        raise SystemExit(f"{path} not found — run evals with --trace first.")

    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not records:
        raise SystemExit("Trace file is empty.")

    total_calls = len(records)
    total_in = sum(r["input_tokens"] for r in records)
    total_out = sum(r["output_tokens"] for r in records)
    avg_latency = sum(r["latency_ms"] for r in records) / total_calls

    by_model: dict[str, list[dict]] = defaultdict(list)
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_model[r["model"]].append(r)
        by_type[r["call_type"]].append(r)

    print(f"Trace: {path}  ({total_calls} calls)\n")
    print(f"{'Totals':<20} input_tok={total_in:,}  output_tok={total_out:,}  avg_latency={avg_latency:.0f}ms\n")

    print(f"{'By model':<20} {'calls':>6}  {'in_tok':>8}  {'out_tok':>8}  {'avg_ms':>8}")
    print("-" * 60)
    for model, recs in sorted(by_model.items()):
        print(
            f"  {model:<18} {len(recs):>6}  "
            f"{sum(r['input_tokens'] for r in recs):>8,}  "
            f"{sum(r['output_tokens'] for r in recs):>8,}  "
            f"{sum(r['latency_ms'] for r in recs)/len(recs):>8.0f}"
        )

    print(f"\n{'By call type':<20} {'calls':>6}  {'in_tok':>8}  {'out_tok':>8}  {'avg_ms':>8}")
    print("-" * 60)
    for ctype, recs in sorted(by_type.items()):
        print(
            f"  {ctype:<18} {len(recs):>6}  "
            f"{sum(r['input_tokens'] for r in recs):>8,}  "
            f"{sum(r['output_tokens'] for r in recs):>8,}  "
            f"{sum(r['latency_ms'] for r in recs)/len(recs):>8.0f}"
        )


if __name__ == "__main__":
    main()
