#!/usr/bin/env python3
"""Live QUIC competing-flow smoke experiment.

Two independent aioquic connections run concurrently over a shared localhost
schedule (no rate shaping in this experiment; see run_quic_emulated_path.py for
the measured shaped-path experiment). One flow sends the
update as a raw QUIC stream. The other sends the same update through ReduLink's
binary QUIC stream mapping. The experiment is intentionally small and
reproducible; it is not an Internet fairness study. It checks that ReduLink's
reconstructed goodput increase is obtained while the constrained link sees only
encoded QUIC traffic.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "prototypes"))

from run_quic_flow_comparison import run_raw_async  # type: ignore
from redulink_aioquic_experiment import demo_payload, run_async as run_redulink_async  # type: ignore


@dataclass
class FlowOutcome:
    method: str
    input_bytes: int
    encoded_stream_payload_bytes: int
    reconstructed_bytes: int
    elapsed_ms: float
    effective_multiplier: float
    reconstruction_ok: bool
    semantic_misses: int = 0
    repair_full_frames: int = 0
    round_id: int = 0
    note: str = ""


async def _run_pair(round_id: int, *, loss_every: int, rate_hint_mbps: float) -> list[FlowOutcome]:
    # The aioquic helpers already provide real encrypted streams and optional
    # datagram loss. We run them concurrently to exercise overlapping transport
    # activity. The rate_hint is recorded as experiment metadata because the
    # artifact uses localhost helpers rather than requiring tc/netns privileges.
    warm, data = demo_payload()
    started = time.perf_counter()
    raw_task = asyncio.create_task(run_raw_async(data, loss_every=loss_every))
    rl_task = asyncio.create_task(run_redulink_async(
        warm=warm,
        data=data,
        chunk_size=1024,
        missing_every=7,
        wire_format="binary",
        loss_every=loss_every,
    ))
    raw, rl = await asyncio.gather(raw_task, rl_task)
    wall_ms = round((time.perf_counter() - started) * 1000, 3)
    raw_elapsed = float(raw.get("client_elapsed_ms", wall_ms))
    rl_elapsed = float(rl.get("client_elapsed_ms", wall_ms))
    return [
        FlowOutcome(
            method="raw-quic-stream",
            input_bytes=int(raw.get("input_bytes", len(data))),
            encoded_stream_payload_bytes=int(raw.get("quic_stream_payload_total_bytes", len(data))),
            reconstructed_bytes=int(raw.get("server_received_bytes", len(data))),
            elapsed_ms=raw_elapsed,
            effective_multiplier=float(raw.get("effective_stream_payload_multiplier", 1.0)),
            reconstruction_ok=bool(raw.get("reconstruction_ok", False)),
            round_id=round_id,
            note=f"concurrent round {round_id}; unshaped localhost schedule; rate_hint_mbps={rate_hint_mbps} is metadata only",
        ),
        FlowOutcome(
            method="redulink-binary-quic-stream",
            input_bytes=int(rl.get("input_bytes", len(data))),
            encoded_stream_payload_bytes=int(rl.get("quic_stream_payload_total_bytes", 0)),
            reconstructed_bytes=int(rl.get("server_reconstructed_bytes", len(data))),
            elapsed_ms=rl_elapsed,
            effective_multiplier=float(rl.get("quic_stream_payload_multiplier_after_repair", 0.0)),
            reconstruction_ok=bool(rl.get("reconstruction_ok", False)),
            semantic_misses=int(rl.get("semantic_misses", 0)),
            repair_full_frames=int(rl.get("repair_full_frames", 0)),
            round_id=round_id,
            note=f"concurrent round {round_id}; unshaped localhost schedule; rate_hint_mbps={rate_hint_mbps} is metadata only",
        ),
    ]


def jain(values: list[float]) -> float:
    if not values or any(v < 0 for v in values):
        return 0.0
    denom = len(values) * sum(v * v for v in values)
    return round((sum(values) ** 2) / denom, 6) if denom else 0.0


async def run(rounds: int, *, loss_every: int, rate_hint_mbps: float) -> dict[str, Any]:
    rows: list[FlowOutcome] = []
    for i in range(rounds):
        rows.extend(await _run_pair(i + 1, loss_every=loss_every, rate_hint_mbps=rate_hint_mbps))
    encoded_balance = []
    reconstructed_balance = []
    for round_id in range(1, rounds + 1):
        pair = [r for r in rows if r.round_id == round_id]
        encoded_rates = []
        reconstructed_rates = []
        for r in pair:
            seconds = max(r.elapsed_ms / 1000.0, 1e-9)
            encoded_rates.append(r.encoded_stream_payload_bytes / seconds)
            reconstructed_rates.append(r.reconstructed_bytes / seconds)
        encoded_balance.append(jain(encoded_rates))
        reconstructed_balance.append(jain(reconstructed_rates))
    mean = lambda values: round(sum(values) / len(values), 6) if values else 0.0
    return {
        "experiment": "concurrent_aioquic_raw_vs_redulink_stream_mapping",
        "scope": "unshaped localhost concurrency diagnostic; no controlled bottleneck and not a fairness or congestion-control study",
        "rounds": rounds,
        "loss_every": loss_every,
        "rate_hint_mbps": rate_hint_mbps,
        "all_reconstructed": all(r.reconstruction_ok for r in rows),
        "encoded_rate_balance_index_mean": mean(encoded_balance),
        "reconstructed_rate_balance_index_mean": mean(reconstructed_balance),
        "per_round_balance_diagnostic": [
            {
                "round": index + 1,
                "encoded_rate_balance_index": encoded_balance[index],
                "reconstructed_rate_balance_index": reconstructed_balance[index],
            }
            for index in range(len(encoded_balance))
        ],
        "rows": [r.__dict__ for r in rows],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rounds", type=int, default=2)
    p.add_argument("--loss-every", type=int, default=9)
    p.add_argument("--rate-hint-mbps", type=float, default=25.0)
    p.add_argument("--output-json", type=Path, default=ROOT / "results" / "quic_competing_flows.json")
    p.add_argument("--output-csv", type=Path, default=ROOT / "results" / "quic_competing_flows.csv")
    args = p.parse_args()
    summary = asyncio.run(run(args.rounds, loss_every=args.loss_every, rate_hint_mbps=args.rate_hint_mbps))
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    rows = summary["rows"]
    with args.output_csv.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({k: summary[k] for k in ["experiment", "all_reconstructed", "encoded_rate_balance_index_mean", "reconstructed_rate_balance_index_mean"]}, indent=2))


if __name__ == "__main__":
    main()
