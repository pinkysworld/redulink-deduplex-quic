#!/usr/bin/env python3
"""Derive the measured ReduLink deployment envelope from committed byte sweeps.

The output is an algebraic restatement of deterministic stream-byte evidence,
not a transport timing model. The script checks every measured miss point
against the inferred linear repair cost before writing the derived result.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"no rows in {path}")
    return rows


def derive(miss_path: Path, scaling_path: Path) -> dict[str, object]:
    miss_rows = read_rows(miss_path)
    scaling_rows = read_rows(scaling_path)
    zero_rows = [row for row in miss_rows if int(row["semantic_misses"]) == 0]
    if len(zero_rows) != 1:
        raise ValueError("miss sweep must contain exactly one zero-miss row")
    zero = zero_rows[0]
    input_bytes = int(zero["input_bytes"])
    initial_refs = int(zero["initial_ref_frames"])
    base_forward = int(zero["forward_protocol_stream_bytes"])
    base_reverse = int(zero["reverse_repair_control_stream_bytes"])
    base_total = int(zero["protocol_stream_bytes"])
    if base_forward + base_reverse != base_total:
        raise ValueError("zero-miss stream accounting does not add up")

    forward_slopes: set[int] = set()
    reverse_slopes: set[int] = set()
    for row in miss_rows:
        misses = int(row["semantic_misses"])
        if misses == 0:
            continue
        forward_delta = int(row["forward_protocol_stream_bytes"]) - base_forward
        reverse_delta = int(row["reverse_repair_control_stream_bytes"]) - base_reverse
        if forward_delta % misses or reverse_delta % misses:
            raise ValueError("repair cost is not integral per semantic miss")
        forward_slopes.add(forward_delta // misses)
        reverse_slopes.add(reverse_delta // misses)
    if len(forward_slopes) != 1 or len(reverse_slopes) != 1:
        raise ValueError("repair cost is not constant across the measured sweep")
    forward_per_miss = forward_slopes.pop()
    reverse_per_miss = reverse_slopes.pop()
    total_per_miss = forward_per_miss + reverse_per_miss

    for row in miss_rows:
        misses = int(row["semantic_misses"])
        expected = base_total + total_per_miss * misses
        if int(row["protocol_stream_bytes"]) != expected:
            raise ValueError(f"measured row with {misses} misses violates the linear model")

    continuous_break_even_misses = (input_bytes - base_total) / total_per_miss
    max_integer_beneficial = math.ceil(continuous_break_even_misses) - 1
    first_nonbeneficial = max_integer_beneficial + 1

    sixteen_mib = [
        row for row in scaling_rows if int(row["input_bytes"]) == 16 * 1024 * 1024
    ]
    if len(sixteen_mib) != 2:
        raise ValueError("capacity sweep must contain both 16 MiB rows")
    by_budget = {
        int(row["endpoint_dictionary_budget_chunks"]): row for row in sixteen_mib
    }
    if set(by_budget) != {8192, 24576}:
        raise ValueError("unexpected 16 MiB capacity budgets")
    overflow = by_budget[8192]
    retained = by_budget[24576]

    return {
        "experiment": "native_quic_deployment_envelope",
        "input_bytes": input_bytes,
        "initial_ref_frames": initial_refs,
        "zero_miss_protocol_bytes": base_total,
        "zero_miss_multiplier": round(input_bytes / base_total, 6),
        "marginal_forward_bytes_per_miss": forward_per_miss,
        "marginal_reverse_bytes_per_miss": reverse_per_miss,
        "marginal_total_bytes_per_miss": total_per_miss,
        "exact_byte_equation": f"B(m)={base_total}+{total_per_miss}m",
        "continuous_break_even_misses": round(continuous_break_even_misses, 6),
        "continuous_break_even_miss_fraction": round(
            continuous_break_even_misses / initial_refs, 6
        ),
        "max_integer_beneficial_misses": max_integer_beneficial,
        "max_integer_beneficial_miss_fraction": round(
            max_integer_beneficial / initial_refs, 6
        ),
        "first_nonbeneficial_misses": first_nonbeneficial,
        "first_nonbeneficial_protocol_bytes": base_total
        + total_per_miss * first_nonbeneficial,
        "measured_rows_match_linear_model": True,
        "capacity_overflow_input_bytes": int(overflow["input_bytes"]),
        "capacity_overflow_budget_chunks": int(
            overflow["endpoint_dictionary_budget_chunks"]
        ),
        "capacity_overflow_initial_ref_frames": int(overflow["initial_ref_frames"]),
        "capacity_overflow_multiplier": float(overflow["stream_payload_multiplier"]),
        "capacity_retained_budget_chunks": int(
            retained["endpoint_dictionary_budget_chunks"]
        ),
        "capacity_retained_initial_ref_frames": int(retained["initial_ref_frames"]),
        "capacity_retained_multiplier": float(retained["stream_payload_multiplier"]),
        "claim_scope": (
            "deterministic native-QUIC application-stream bytes only; deployment also "
            "requires the warm working set to remain resident; no latency, fairness, "
            "packet, or production-workload inference"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--miss-csv",
        type=Path,
        default=ROOT / "results" / "quic_miss_rate_sensitivity.csv",
    )
    parser.add_argument(
        "--scaling-csv",
        type=Path,
        default=ROOT / "results" / "aioquic_scaling_experiment.csv",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=ROOT / "results" / "deployment_envelope.csv",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=ROOT / "results" / "deployment_envelope.json",
    )
    args = parser.parse_args()
    result = derive(args.miss_csv, args.scaling_csv)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result), lineterminator="\n")
        writer.writeheader()
        writer.writerow(result)
    args.output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(args.output_csv)


if __name__ == "__main__":
    main()
