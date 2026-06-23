"""Lightweight JSONL tracing for eval runs.

Each LLM call appends one record to a trace file. trace_summary.py reads
it and prints aggregates. Tracing is opt-in and non-fatal — a write failure
never breaks the eval.

Record shape:
  ts, model, scenario_id, input_tokens, output_tokens, latency_ms, call_type
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_TRACE_PATH = Path("evals/traces.jsonl")


@dataclass
class TraceRecord:
    ts: str
    model: str
    scenario_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    call_type: str  # "recommend" or "judge"


def write(record: TraceRecord, path: Path = DEFAULT_TRACE_PATH) -> None:
    try:
        with path.open("a") as f:
            f.write(json.dumps(asdict(record)) + "\n")
    except OSError:
        pass


def timed_generate(llm, system: str, user: str, scenario_id: str, call_type: str,
                   trace_path: Path = DEFAULT_TRACE_PATH) -> str:
    """Wrap llm.generate() with timing and trace write."""
    t0 = time.perf_counter()
    result = llm.generate(system, user)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if hasattr(llm, "last_usage") and llm.last_usage:
        write(TraceRecord(
            ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            model=getattr(llm, "_model", "unknown"),
            scenario_id=scenario_id,
            input_tokens=llm.last_usage.input_tokens,
            output_tokens=llm.last_usage.output_tokens,
            latency_ms=elapsed_ms,
            call_type=call_type,
        ), path=trace_path)

    return result
