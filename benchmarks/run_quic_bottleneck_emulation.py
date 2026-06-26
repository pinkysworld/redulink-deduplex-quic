#!/usr/bin/env python3
"""Portable bottleneck-emulation analysis for raw QUIC and ReduLink-over-QUIC.

This script is deliberately unprivileged: it does not require Linux tc/netns.
It uses measured stream-payload bytes from the native aioquic experiments and
applies the same bottleneck service rate to the encoded stream payloads. The
result is an accounting-and-scheduling emulation, not a replacement for a full
kernel network-emulator experiment. It answers the journal-review question that
ReduLink's reconstructed goodput advantage comes from fewer encoded bytes, not
from asking congestion control to send more bytes.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def jain(xs):
    if not xs:
        return 0.0
    denom = len(xs) * sum(x*x for x in xs)
    return (sum(xs) ** 2 / denom) if denom else 0.0


def load_flow_bytes(path: Path):
    rows = list(csv.DictReader(path.open()))
    chosen = {}
    for r in rows:
        if r.get("loss_every", "0") in ("0", "0.0"):
            chosen[r["method"]] = r
    return chosen


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-csv", type=Path, default=ROOT / "results" / "quic_flow_comparison.csv")
    p.add_argument("--rates-mbps", type=float, nargs="+", default=[10.0, 25.0, 100.0])
    p.add_argument("--rtt-ms", type=float, nargs="+", default=[10.0, 50.0])
    p.add_argument("--output-csv", type=Path, default=ROOT / "results" / "quic_bottleneck_emulation.csv")
    p.add_argument("--output-json", type=Path, default=ROOT / "results" / "quic_bottleneck_emulation.json")
    args = p.parse_args()
    chosen = load_flow_bytes(args.input_csv)
    if "raw-quic-stream" not in chosen or "redulink-binary-quic-stream" not in chosen:
        raise SystemExit("quic_flow_comparison.csv must contain raw-quic-stream and redulink-binary-quic-stream rows")
    flows = []
    for method in ["raw-quic-stream", "redulink-binary-quic-stream"]:
        row = chosen[method]
        flows.append({
            "method": method,
            "input_bytes": int(float(row["input_bytes"])),
            "encoded_stream_bytes": int(float(row["stream_payload_bytes"])),
            "reconstructed_bytes": int(float(row["input_bytes"])),
        })
    out = []
    for rate in args.rates_mbps:
        rate_Bps = rate * 1_000_000 / 8.0
        for rtt in args.rtt_ms:
            # A simple fair-share fluid model: while both flows are active they
            # each receive half the encoded bottleneck service rate. The shorter
            # encoded flow completes first; the remaining flow then gets the full
            # service rate. RTT is added once as a conservative connection/setup
            # and completion acknowledgement term.
            sorted_flows = sorted(flows, key=lambda f: f["encoded_stream_bytes"])
            short, long = sorted_flows
            t_short = short["encoded_stream_bytes"] / (rate_Bps / 2.0)
            long_remaining = max(0.0, long["encoded_stream_bytes"] - short["encoded_stream_bytes"])
            t_long = t_short + long_remaining / rate_Bps
            finish = {short["method"]: t_short + rtt/1000.0, long["method"]: t_long + rtt/1000.0}
            encoded_rates = []
            reconstructed_rates = []
            encoded_jain = None
            reconstructed_jain = None
            scenario_rows = []
            for f in flows:
                elapsed = finish[f["method"]]
                encoded_rates.append(f["encoded_stream_bytes"] / elapsed)
                reconstructed_rates.append(f["reconstructed_bytes"] / elapsed)
                scenario_rows.append({
                    "rate_mbps": rate,
                    "rtt_ms": rtt,
                    "method": f["method"],
                    "input_bytes": f["input_bytes"],
                    "encoded_stream_bytes": f["encoded_stream_bytes"],
                    "completion_ms_emulated": round(elapsed * 1000, 3),
                    "encoded_goodput_mbps_emulated": round((f["encoded_stream_bytes"] * 8 / elapsed) / 1_000_000, 6),
                    "reconstructed_goodput_mbps_emulated": round((f["reconstructed_bytes"] * 8 / elapsed) / 1_000_000, 6),
                    "model": "fluid fair-share bottleneck over measured QUIC stream payload bytes",
                })
            encoded_jain = round(jain(encoded_rates), 6)
            reconstructed_jain = round(jain(reconstructed_rates), 6)
            for row in scenario_rows:
                row["encoded_rate_jain_index_scenario"] = encoded_jain
                row["reconstructed_rate_jain_index_scenario"] = reconstructed_jain
                out.append(row)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()), lineterminator="\n", extrasaction="ignore")
        w.writeheader(); w.writerows(out)
    args.output_json.write_text(json.dumps({"scope": "portable bottleneck emulation over measured aioquic stream payload bytes", "rows": out}, indent=2, sort_keys=True) + "\n")
    print(args.output_csv)


if __name__ == "__main__":
    main()
