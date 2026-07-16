#!/usr/bin/env python3
"""Measure paired endpoint CPU and local throughput scaling for raw and ReduLink QUIC.

The benchmark uses one process containing both endpoints, a fresh verified QUIC
connection per transfer, matched warm dictionaries, and paired order-alternated
runs. Process CPU starts immediately before connect and includes live exporter
use plus ReduLink encoding/dictionary preparation performed in the connection.
Local completion time is reported as implementation scaling evidence, not WAN
latency evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import datetime, timezone
import gc
import json
import platform
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "prototypes"))

from run_quic_flow_comparison import run_raw_async  # type: ignore
from redulink_aioquic_experiment import (  # type: ignore
    SEND_DRAIN_BYTES,
    demo_payload,
    run_async as run_redulink_async,
)
from stats_utils import bootstrap_ci, mean, median, round_float, stdev  # type: ignore

DEFAULT_BLOCKS = [64, 256, 1024, 4096, 16384, 32768]
DEFAULT_ROUNDS = 10


def row_from_stats(
    *,
    blocks: int,
    round_id: int,
    execution_order: int,
    method: str,
    stats: dict[str, Any],
) -> dict[str, Any]:
    input_bytes = int(stats["input_bytes"])
    completion_ms = float(stats["client_network_elapsed_ms"])
    cpu_ms = float(stats["combined_endpoint_process_cpu_ms"])
    return {
        "payload_blocks": blocks,
        "input_bytes": input_bytes,
        "input_mib": round(input_bytes / (1024 * 1024), 6),
        "round": round_id,
        "execution_order": execution_order,
        "method": method,
        "client_completion_ms": round(completion_ms, 3),
        "combined_endpoint_process_cpu_ms": round(cpu_ms, 3),
        "combined_endpoint_process_cpu_ms_per_mib": round(
            cpu_ms / (input_bytes / (1024 * 1024)), 6,
        ),
        "reconstructed_throughput_mib_s": round(
            (input_bytes / (1024 * 1024)) / (completion_ms / 1000.0), 6,
        ),
        "encoded_stream_payload_bytes": int(stats["quic_stream_payload_total_bytes"]),
        "stream_payload_multiplier": round(
            input_bytes / int(stats["quic_stream_payload_total_bytes"]), 6,
        ),
        "client_ttfb_ms": float(stats["client_time_to_first_reconstructed_byte_ms"]),
        "reconstruction_ok": bool(stats["reconstruction_ok"]),
        "congestion_control_algorithm": str(stats["congestion_control_algorithm"]),
        "tls_exporter_live": stats.get("tls_exporter_live", "not-applicable"),
        "tls_exporter_outputs_match": stats.get("tls_exporter_outputs_match", "not-applicable"),
    }


async def run_pair(
    *,
    blocks: int,
    round_id: int,
    congestion_control_algorithm: str,
) -> list[dict[str, Any]]:
    warm, data = demo_payload(blocks)
    dictionary_budget = max(8192, blocks + 256)

    async def raw() -> dict[str, Any]:
        return await run_raw_async(
            data,
            congestion_control_algorithm=congestion_control_algorithm,
        )

    async def redulink() -> dict[str, Any]:
        return await run_redulink_async(
            warm=warm,
            data=data,
            chunk_size=1024,
            missing_every=0,
            wire_format="binary",
            sender_max_dict_chunks=dictionary_budget,
            receiver_max_dict_chunks=dictionary_budget,
            congestion_control_algorithm=congestion_control_algorithm,
        )

    methods: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {
        "raw-quic-stream": raw,
        "redulink-binary-quic-stream": redulink,
    }
    order = (
        ["raw-quic-stream", "redulink-binary-quic-stream"]
        if round_id % 2
        else ["redulink-binary-quic-stream", "raw-quic-stream"]
    )
    rows = []
    for execution_order, method in enumerate(order, start=1):
        gc.collect()
        await asyncio.sleep(0)
        rows.append(row_from_stats(
            blocks=blocks,
            round_id=round_id,
            execution_order=execution_order,
            method=method,
            stats=await methods[method](),
        ))
    return rows


def _ratio_fields(prefix: str, values: list[float]) -> dict[str, Any]:
    low, high = bootstrap_ci(values)
    median_low, median_high = bootstrap_ci(values, statistic="median")
    return {
        f"{prefix}_ratio_mean": round_float(mean(values)),
        f"{prefix}_ratio_median": round_float(median(values)),
        f"{prefix}_ratio_sd": round_float(stdev(values)),
        f"{prefix}_ratio_ci95_low": round_float(low),
        f"{prefix}_ratio_ci95_high": round_float(high),
        f"{prefix}_ratio_median_ci95_low": round_float(median_low),
        f"{prefix}_ratio_median_ci95_high": round_float(median_high),
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_size: dict[int, dict[int, dict[str, dict[str, Any]]]] = {}
    for row in rows:
        by_size.setdefault(int(row["payload_blocks"]), {}).setdefault(
            int(row["round"]), {},
        )[str(row["method"])] = row
    summaries = []
    metric_fields = {
        "completion": "client_completion_ms",
        "process_cpu": "combined_endpoint_process_cpu_ms",
        "cpu_per_mib": "combined_endpoint_process_cpu_ms_per_mib",
        "reconstructed_throughput": "reconstructed_throughput_mib_s",
        "stream_bytes": "encoded_stream_payload_bytes",
    }
    for blocks, rounds in sorted(by_size.items()):
        ratios: dict[str, list[float]] = {name: [] for name in metric_fields}
        paired = []
        for pair in rounds.values():
            raw = pair.get("raw-quic-stream")
            redulink = pair.get("redulink-binary-quic-stream")
            if raw is None or redulink is None:
                continue
            paired.extend([raw, redulink])
            for name, field in metric_fields.items():
                denominator = float(raw[field])
                if denominator > 0:
                    ratios[name].append(float(redulink[field]) / denominator)
        summary: dict[str, Any] = {
            "payload_blocks": blocks,
            "input_bytes": blocks * 1024,
            "input_mib": round(blocks / 1024, 6),
            "paired_rounds": len(ratios["completion"]),
            "all_reconstructed": all(bool(row["reconstruction_ok"]) for row in paired),
            "ratio_definition": "paired ReduLink value divided by paired raw-QUIC value",
        }
        for name, values in ratios.items():
            summary.update(_ratio_fields(name, values))
        summaries.append(summary)
    return summaries


async def run_experiment(
    *,
    blocks: list[int],
    rounds: int,
    warmups: int,
    congestion_control_algorithm: str,
) -> dict[str, Any]:
    rows = []
    for size in blocks:
        for warmup in range(warmups):
            await run_pair(
                blocks=size,
                round_id=warmup + 1,
                congestion_control_algorithm=congestion_control_algorithm,
            )
        for round_id in range(1, rounds + 1):
            rows.extend(await run_pair(
                blocks=size,
                round_id=round_id,
                congestion_control_algorithm=congestion_control_algorithm,
            ))
    import aioquic  # type: ignore

    return {
        "experiment": "cpu_throughput_scaling_v3_17",
        "scope": (
            "combined in-process client plus server CPU and localhost implementation throughput; "
            "fresh verified QUIC connection per transfer; not a WAN latency claim"
        ),
        "cpu_boundary": (
            "process_time from immediately before connect through receipt of the exact final result; "
            "ReduLink includes exporter use, frame encoding, dictionary construction, verification, and reconstruction"
        ),
        "parameters": {
            "blocks": blocks,
            "block_bytes": 1024,
            "rounds": rounds,
            "warmups": warmups,
            "congestion_control_algorithm": congestion_control_algorithm,
            "receiver_missing_every": 0,
            "dictionary_budget": "matched endpoints; max(8192, payload_blocks + 256)",
            "sender_drain_batch_bytes": SEND_DRAIN_BYTES,
            "full_gc_before_each_transfer": True,
        },
        "provenance": {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(),
            "python": sys.version,
            "aioquic_version": aioquic.__version__,
        },
        "rows": rows,
        "summary": summarize(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blocks", type=int, nargs="+", default=DEFAULT_BLOCKS)
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--congestion-control", choices=["reno", "cubic"], default="reno")
    parser.add_argument(
        "--output-json", type=Path,
        default=ROOT / "results" / "cpu_throughput_scaling_v3_17.json",
    )
    parser.add_argument(
        "--output-csv", type=Path,
        default=ROOT / "results" / "cpu_throughput_scaling_v3_17.csv",
    )
    parser.add_argument(
        "--output-summary-csv", type=Path,
        default=ROOT / "results" / "cpu_throughput_scaling_v3_17_summary.csv",
    )
    args = parser.parse_args()
    if args.rounds < 1 or args.warmups < 0 or any(block < 16 for block in args.blocks):
        raise SystemExit("rounds must be positive, warmups non-negative, and blocks at least 16")
    result = asyncio.run(run_experiment(
        blocks=args.blocks,
        rounds=args.rounds,
        warmups=args.warmups,
        congestion_control_algorithm=args.congestion_control,
    ))
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result["rows"][0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(result["rows"])
    with args.output_summary_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result["summary"][0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(result["summary"])
    print(args.output_json)


if __name__ == "__main__":
    main()
