#!/usr/bin/env python3
"""Measured userspace path emulation for competing QUIC flows.

A raw QUIC flow and a ReduLink binary-stream flow run concurrently, each through
its own localhost UDP proxy, while BOTH proxies share one PathShaper: a userspace
token-bucket serializer plus one-way propagation delay. This emulates the two
flows competing for a single bottleneck link of configurable rate and RTT.

This is a real measurement of aioquic traffic through an emulated path, not an
analytic model. It is also not kernel tc/netem: shaping happens in the asyncio
event loop, so very high rates or very low delays are limited by scheduler
granularity. Rates <= 50 Mbps and RTTs >= 20 ms are comfortably within its
fidelity range on a commodity host.

Outputs: results/quic_emulated_path.csv and .json.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "prototypes"))

from run_quic_flow_comparison import run_raw_async  # type: ignore
from redulink_aioquic_experiment import demo_payload, run_async as run_redulink_async  # type: ignore
from run_quic_competing_flows import jain  # type: ignore


class PathShaper:
    """Shared token-bucket serializer + one-way delay for proxied datagrams."""

    def __init__(self, rate_mbps: float, one_way_delay_ms: float) -> None:
        self.rate_bps = rate_mbps * 1e6
        self.delay_s = one_way_delay_ms / 1000.0
        self._next_free: float = 0.0
        self.bytes_shaped = 0
        self.datagrams_shaped = 0
        self.total_queue_delay_s = 0.0
        self.max_queue_delay_s = 0.0

    def schedule(self, nbytes: int) -> float:
        loop = asyncio.get_event_loop()
        now = loop.time()
        start = max(now, self._next_free)
        q = start - now
        self.total_queue_delay_s += q
        if q > self.max_queue_delay_s:
            self.max_queue_delay_s = q
        self._next_free = start + (nbytes * 8) / self.rate_bps
        self.bytes_shaped += nbytes
        self.datagrams_shaped += 1
        return self._next_free + self.delay_s


async def run_scenario(rate_mbps: float, rtt_ms: float, *, loss_every: int, rounds: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    shaper_stats = []
    for rnd in range(1, rounds + 1):
        shaper = PathShaper(rate_mbps, rtt_ms / 2.0)
        warm, data = demo_payload()
        started = time.perf_counter()
        raw_task = asyncio.create_task(run_raw_async(data, loss_every=loss_every, shaper=shaper))
        rl_task = asyncio.create_task(run_redulink_async(
            warm=warm, data=data, chunk_size=1024, missing_every=7,
            wire_format="binary", loss_every=loss_every, shaper=shaper,
        ))
        raw, rl = await asyncio.gather(raw_task, rl_task)
        wall_ms = round((time.perf_counter() - started) * 1000, 3)
        shaper_stats.append({
            "mean_queue_delay_ms": round(1000 * shaper.total_queue_delay_s / max(shaper.datagrams_shaped, 1), 3),
            "max_queue_delay_ms": round(1000 * shaper.max_queue_delay_s, 3),
        })
        for method, st, enc_key, recon_key in (
            ("raw-quic-stream", raw, "quic_stream_payload_total_bytes", "server_received_bytes"),
            ("redulink-binary-quic-stream", rl, "quic_stream_payload_total_bytes", "server_reconstructed_bytes"),
        ):
            elapsed = float(st.get("client_elapsed_ms", wall_ms))
            enc = int(st.get(enc_key, 0))
            recon = int(st.get(recon_key, 0))
            rows.append({
                "rate_mbps": rate_mbps, "rtt_ms": rtt_ms, "loss_every": loss_every, "round": rnd,
                "method": method,
                "input_bytes": int(st.get("input_bytes", len(data))),
                "encoded_stream_payload_bytes": enc,
                "reconstructed_bytes": recon,
                "completion_ms_measured": round(elapsed, 3),
                "encoded_rate_mbps_measured": round(enc * 8 / (elapsed / 1000.0) / 1e6, 6) if elapsed else 0.0,
                "reconstructed_rate_mbps_measured": round(recon * 8 / (elapsed / 1000.0) / 1e6, 6) if elapsed else 0.0,
                "reconstruction_ok": bool(st.get("reconstruction_ok", False)),
                "semantic_misses": int(st.get("semantic_misses", 0)),
                "repair_full_frames": int(st.get("repair_full_frames", 0)),
                "emulation": "userspace token-bucket + one-way delay shared by both flows; not kernel netem",
                "mean_queue_delay_ms": shaper_stats[-1]["mean_queue_delay_ms"],
                "max_queue_delay_ms": shaper_stats[-1]["max_queue_delay_ms"],
            })
    return rows


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    grid = [(5.0, 20.0), (5.0, 80.0), (20.0, 20.0), (20.0, 80.0)]
    all_rows: list[dict[str, Any]] = []
    for rate, rtt in grid:
        all_rows.extend(await run_scenario(rate, rtt, loss_every=args.loss_every, rounds=args.rounds))
    # per-scenario summary
    summary = []
    for rate, rtt in grid:
        sel = [r for r in all_rows if r["rate_mbps"] == rate and r["rtt_ms"] == rtt]
        raw = [r for r in sel if r["method"] == "raw-quic-stream"]
        rl = [r for r in sel if r["method"] != "raw-quic-stream"]
        mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
        summary.append({
            "rate_mbps": rate, "rtt_ms": rtt, "rounds": args.rounds, "loss_every": args.loss_every,
            "raw_completion_ms_mean": round(mean([r["completion_ms_measured"] for r in raw]), 3),
            "redulink_completion_ms_mean": round(mean([r["completion_ms_measured"] for r in rl]), 3),
            "raw_app_rate_mbps_mean": round(mean([r["reconstructed_rate_mbps_measured"] for r in raw]), 3),
            "redulink_app_rate_mbps_mean": round(mean([r["reconstructed_rate_mbps_measured"] for r in rl]), 3),
            "encoded_rate_jain_index": jain([mean([r["encoded_rate_mbps_measured"] for r in raw]),
                                             mean([r["encoded_rate_mbps_measured"] for r in rl])]),
            "all_reconstructed": all(r["reconstruction_ok"] for r in sel),
            "mean_queue_delay_ms": round(sum(r["mean_queue_delay_ms"] for r in sel) / len(sel), 3),
            "max_queue_delay_ms": round(max(r["max_queue_delay_ms"] for r in sel), 3),
        })
    return {"experiment": "measured_userspace_path_emulation_competing_flows",
            "note": "both flows share one token-bucket + delay path; asyncio userspace shaping, not kernel netem",
            "rows": all_rows, "summary": summary}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--loss-every", type=int, default=0)
    ap.add_argument("--output-json", type=Path, default=ROOT / "results" / "quic_emulated_path.json")
    ap.add_argument("--output-csv", type=Path, default=ROOT / "results" / "quic_emulated_path.csv")
    args = ap.parse_args()
    result = asyncio.run(main_async(args))
    args.output_json.write_text(json.dumps(result, indent=2))
    rows = result["rows"]
    with args.output_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    for s in result["summary"]:
        print(s)
    print(args.output_csv)


if __name__ == "__main__":
    main()
