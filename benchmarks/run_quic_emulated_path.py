#!/usr/bin/env python3
"""Measured full-duplex userspace path emulation for competing QUIC flows.

A raw QUIC flow and a ReduLink binary-stream flow run concurrently. Both flows
share ONE PathShaper (a single emulated bottleneck link), but the shaper models
a FULL-DUPLEX link: forward (client->server) and reverse (server->client)
directions have independent token buckets, so ACK/MISS reverse traffic does not
serialize behind forward data (this corrects the half-duplex artifact of the
earlier single-bucket shaper). One-way propagation delay is added per datagram.

This is a real measurement of aioquic traffic through an emulated path; it is
NOT kernel tc/netem (shaping runs in the asyncio loop, so very high rates or
very low delays are scheduler-limited; rates <= 20 Mbps and RTTs >= 20 ms are
within fidelity). Multiple rounds per point give dispersion, not just means.

`--payload` selects the transferred bytes:
  demo  : constructed byte-stable warm/update (default, comparable to prior runs)
  redis : real public Redis-layered warm/update bytes from
          data/external_positive_corpora (author-independent content).

Outputs: results/quic_emulated_path.csv and .json (means + stdev + all rows).
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
from redulink_aioquic_experiment import demo_payload, run_async as run_redulink_async  # type: ignore
from run_quic_competing_flows import jain  # type: ignore


class PathShaper:
    """Shared full-duplex bottleneck: independent token bucket per direction."""

    def __init__(self, rate_mbps: float, one_way_delay_ms: float) -> None:
        self.rate_bps = rate_mbps * 1e6
        self.delay_s = one_way_delay_ms / 1000.0
        self._next_free = {"c2s": 0.0, "s2c": 0.0}
        self.bytes_shaped = 0
        self.datagrams_shaped = 0
        self.total_queue_delay_s = 0.0
        self.max_queue_delay_s = 0.0

    def schedule(self, nbytes: int, *, direction: str = "c2s") -> float:
        loop = asyncio.get_event_loop()
        now = loop.time()
        start = max(now, self._next_free.get(direction, 0.0))
        q = start - now
        self.total_queue_delay_s += q
        if q > self.max_queue_delay_s:
            self.max_queue_delay_s = q
        self._next_free[direction] = start + (nbytes * 8) / self.rate_bps
        self.bytes_shaped += nbytes
        self.datagrams_shaped += 1
        return self._next_free[direction] + self.delay_s


def _load_payload(kind: str) -> tuple[bytes, bytes, str]:
    if kind == "redis":
        base = ROOT / "data" / "external_positive_corpora" / "redis-layered-public-positive"
        warm = (base / "warm.bin").read_bytes()
        update = (base / "update.bin").read_bytes()
        return warm, update, "real Redis-layered public bytes"
    warm, update = demo_payload()
    return warm, update, "constructed byte-stable demo"


async def run_scenario(rate_mbps: float, rtt_ms: float, *, loss_every: int, rounds: int,
                       payload: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    warm, data, _ = _load_payload(payload)
    chunk = 1024
    missing_every = 7
    for rnd in range(1, rounds + 1):
        shaper = PathShaper(rate_mbps, rtt_ms / 2.0)
        raw_task = asyncio.create_task(run_raw_async(data, loss_every=loss_every, shaper=shaper))
        rl_task = asyncio.create_task(run_redulink_async(
            warm=warm, data=data, chunk_size=chunk, missing_every=missing_every,
            wire_format="binary", loss_every=loss_every, shaper=shaper,
        ))
        raw, rl = await asyncio.gather(raw_task, rl_task)
        qd_mean = 1000 * shaper.total_queue_delay_s / max(shaper.datagrams_shaped, 1)
        qd_max = 1000 * shaper.max_queue_delay_s
        for method, st, enc_key, recon_key in (
            ("raw-quic-stream", raw, "quic_stream_payload_total_bytes", "server_received_bytes"),
            ("redulink-binary-quic-stream", rl, "quic_stream_payload_total_bytes", "server_reconstructed_bytes"),
        ):
            elapsed = float(st.get("client_elapsed_ms", 0.0))
            enc = int(st.get(enc_key, 0)); recon = int(st.get(recon_key, 0))
            rows.append({
                "payload": payload, "rate_mbps": rate_mbps, "rtt_ms": rtt_ms,
                "loss_every": loss_every, "round": rnd, "method": method,
                "input_bytes": int(st.get("input_bytes", len(data))),
                "encoded_stream_payload_bytes": enc, "reconstructed_bytes": recon,
                "completion_ms_measured": round(elapsed, 3),
                "reconstructed_rate_mbps_measured": round(recon * 8 / (elapsed / 1000.0) / 1e6, 6) if elapsed else 0.0,
                "encoded_rate_mbps_measured": round(enc * 8 / (elapsed / 1000.0) / 1e6, 6) if elapsed else 0.0,
                "reconstruction_ok": bool(st.get("reconstruction_ok", False)),
                "semantic_misses": int(st.get("semantic_misses", 0)),
                "mean_queue_delay_ms": round(qd_mean, 3), "max_queue_delay_ms": round(qd_max, 3),
                "emulation": "full-duplex userspace token bucket per direction + one-way delay, shared by both flows; not kernel netem",
            })
    return rows


def _sd(xs: list[float]) -> float:
    return round(statistics.stdev(xs), 3) if len(xs) > 1 else 0.0


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    grid = [(5.0, 20.0), (5.0, 80.0), (20.0, 20.0), (20.0, 80.0)]
    all_rows: list[dict[str, Any]] = []
    for rate, rtt in grid:
        all_rows.extend(await run_scenario(rate, rtt, loss_every=args.loss_every,
                                           rounds=args.rounds, payload=args.payload))
    summary = []
    for rate, rtt in grid:
        sel = [r for r in all_rows if r["rate_mbps"] == rate and r["rtt_ms"] == rtt]
        raw = [r for r in sel if r["method"] == "raw-quic-stream"]
        rl = [r for r in sel if r["method"] != "raw-quic-stream"]
        rawc = [r["completion_ms_measured"] for r in raw]
        rlc = [r["completion_ms_measured"] for r in rl]
        mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else 0.0
        summary.append({
            "payload": args.payload, "rate_mbps": rate, "rtt_ms": rtt,
            "rounds": args.rounds, "loss_every": args.loss_every,
            "raw_completion_ms_mean": mean(rawc), "raw_completion_ms_sd": _sd(rawc),
            "redulink_completion_ms_mean": mean(rlc), "redulink_completion_ms_sd": _sd(rlc),
            "rl_over_raw_completion": round(mean(rlc) / mean(rawc), 3) if mean(rawc) else 0.0,
            "raw_app_rate_mbps_mean": mean([r["reconstructed_rate_mbps_measured"] for r in raw]),
            "redulink_app_rate_mbps_mean": mean([r["reconstructed_rate_mbps_measured"] for r in rl]),
            "encoded_rate_jain_index": jain([mean([r["encoded_rate_mbps_measured"] for r in raw]),
                                             mean([r["encoded_rate_mbps_measured"] for r in rl])]),
            "mean_queue_delay_ms": mean([r["mean_queue_delay_ms"] for r in sel]),
            "all_reconstructed": all(r["reconstruction_ok"] for r in sel),
        })
    return {"experiment": "measured_fullduplex_path_emulation_competing_flows",
            "payload": args.payload,
            "note": "both flows share one full-duplex (per-direction) token-bucket + delay path; asyncio userspace shaping, not kernel netem",
            "rows": all_rows, "summary": summary}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--loss-every", type=int, default=0)
    ap.add_argument("--payload", choices=["demo", "redis"], default="demo")
    ap.add_argument("--output-json", type=Path, default=ROOT / "results" / "quic_emulated_path.json")
    ap.add_argument("--output-csv", type=Path, default=ROOT / "results" / "quic_emulated_path.csv")
    args = ap.parse_args()
    result = asyncio.run(main_async(args))
    args.output_json.write_text(json.dumps(result, indent=2))
    rows = result["rows"]
    with args.output_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    for sm in result["summary"]:
        print(sm)
    print(args.output_csv)


if __name__ == "__main__":
    main()
