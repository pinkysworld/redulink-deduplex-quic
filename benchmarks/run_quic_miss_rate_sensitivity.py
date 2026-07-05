#!/usr/bin/env python3
"""Miss-rate sensitivity sweep for the measured QUIC path-emulation harness.

The full-duplex path-emulation result shows two endpoints of the repair story:
byte-stable demo bytes benefit on a constrained shared path, while the real
Redis-layered payload loses time when 72 semantic MISS/FULL repairs are needed.
This sweep keeps the same native aioquic stream mapping and full-duplex
userspace shaper, then varies receiver dictionary thinning on the demo payload
to expose the transition between those regimes.

This is still a localhost userspace emulation, not kernel tc/netem or Mininet.
It is intended as a reviewer-readable sensitivity check, not a production
congestion-control claim.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "prototypes"))

from run_quic_flow_comparison import run_raw_async  # type: ignore
from run_quic_emulated_path import PathShaper  # type: ignore
from redulink_aioquic_experiment import demo_payload, run_async as run_redulink_async  # type: ignore


def _mean(xs: list[float]) -> float:
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def _sd(xs: list[float]) -> float:
    return round(statistics.stdev(xs), 3) if len(xs) > 1 else 0.0


async def run_round(*, missing_every: int, rate_mbps: float, rtt_ms: float,
                    loss_every: int, blocks: int) -> dict[str, Any]:
    warm, data = demo_payload(blocks)
    shaper = PathShaper(rate_mbps, rtt_ms / 2.0)
    raw_task = asyncio.create_task(run_raw_async(data, loss_every=loss_every, shaper=shaper))
    rl_task = asyncio.create_task(
        run_redulink_async(
            warm=warm,
            data=data,
            chunk_size=1024,
            missing_every=missing_every,
            wire_format="binary",
            loss_every=loss_every,
            shaper=shaper,
        )
    )
    raw, rl = await asyncio.gather(raw_task, rl_task)
    ref_frames = int(rl.get("client_ref_frames_initial", 0))
    misses = int(rl.get("semantic_misses", 0))
    raw_ms = float(raw.get("client_elapsed_ms", 0.0))
    rl_ms = float(rl.get("client_elapsed_ms", 0.0))
    return {
        "missing_every": missing_every,
        "input_bytes": int(rl.get("input_bytes", len(data))),
        "ref_frames": ref_frames,
        "semantic_misses": misses,
        "miss_fraction": round(misses / ref_frames, 6) if ref_frames else 0.0,
        "raw_completion_ms": round(raw_ms, 3),
        "redulink_completion_ms": round(rl_ms, 3),
        "rl_over_raw_completion": round(rl_ms / raw_ms, 6) if raw_ms else 0.0,
        "redulink_stream_multiplier": float(rl.get("quic_stream_payload_multiplier_after_repair", 0.0)),
        "reconstruction_ok": bool(raw.get("reconstruction_ok")) and bool(rl.get("reconstruction_ok")),
    }


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for missing_every in args.missing_every:
        for rnd in range(1, args.rounds + 1):
            row = await run_round(
                missing_every=missing_every,
                rate_mbps=args.rate_mbps,
                rtt_ms=args.rtt_ms,
                loss_every=args.loss_every,
                blocks=args.blocks,
            )
            row["round"] = rnd
            rows.append(row)

    summary: list[dict[str, Any]] = []
    for missing_every in args.missing_every:
        sel = [r for r in rows if r["missing_every"] == missing_every]
        summary.append({
            "payload": "demo",
            "rate_mbps": args.rate_mbps,
            "rtt_ms": args.rtt_ms,
            "rounds": args.rounds,
            "missing_every": missing_every,
            "semantic_misses_mean": _mean([float(r["semantic_misses"]) for r in sel]),
            "miss_fraction_mean": _mean([float(r["miss_fraction"]) for r in sel]),
            "raw_completion_ms_mean": _mean([float(r["raw_completion_ms"]) for r in sel]),
            "raw_completion_ms_sd": _sd([float(r["raw_completion_ms"]) for r in sel]),
            "redulink_completion_ms_mean": _mean([float(r["redulink_completion_ms"]) for r in sel]),
            "redulink_completion_ms_sd": _sd([float(r["redulink_completion_ms"]) for r in sel]),
            "rl_over_raw_completion_mean": _mean([float(r["rl_over_raw_completion"]) for r in sel]),
            "redulink_stream_multiplier_mean": _mean([float(r["redulink_stream_multiplier"]) for r in sel]),
            "all_reconstructed": all(bool(r["reconstruction_ok"]) for r in sel),
        })

    return {
        "experiment": "measured_quic_miss_rate_sensitivity",
        "note": "native aioquic streams over a full-duplex userspace token-bucket path; not kernel tc/netem",
        "rows": rows,
        "summary": summary,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rate-mbps", type=float, default=5.0)
    ap.add_argument("--rtt-ms", type=float, default=20.0)
    ap.add_argument("--loss-every", type=int, default=0)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--blocks", type=int, default=96)
    ap.add_argument("--missing-every", type=int, nargs="+", default=[0, 16, 8, 4, 2])
    ap.add_argument("--output-json", type=Path, default=ROOT / "results" / "quic_miss_rate_sensitivity.json")
    ap.add_argument("--output-csv", type=Path, default=ROOT / "results" / "quic_miss_rate_sensitivity.csv")
    args = ap.parse_args()
    result = asyncio.run(main_async(args))

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with args.output_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(result["summary"][0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(result["summary"])
    for row in result["summary"]:
        print(row)
    print(args.output_csv)


if __name__ == "__main__":
    main()
