#!/usr/bin/env python3
"""Run native aioquic ReduLink stream-mapping scaling experiments.

The experiment repeats the same warm/update construction at increasing byte
sizes. It measures QUIC stream-payload bytes rather than UDP/IP packet bytes.
This keeps the result portable in unprivileged artifact-review environments
while still exercising a real aioquic handshake, encrypted stream delivery,
semantic MISS/FULL repair, and byte-exact reconstruction.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototypes"))

try:
    from redulink_aioquic_experiment import run_experiment
except SystemExit as exc:  # pragma: no cover
    raise SystemExit(str(exc))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--blocks", type=int, nargs="+", default=[96, 512, 1024])
    p.add_argument("--loss-every", type=int, default=0)
    p.add_argument("--output-csv", type=Path, default=ROOT / "results" / "aioquic_scaling_experiment.csv")
    p.add_argument("--output-json", type=Path, default=ROOT / "results" / "aioquic_scaling_experiment.json")
    args = p.parse_args()
    rows = []
    results = []
    for blocks in args.blocks:
        stats = run_experiment(payload_blocks=blocks, wire_format="binary", loss_every=args.loss_every)
        results.append(stats)
        rows.append({
            "payload_blocks": blocks,
            "input_bytes": stats["input_bytes"],
            "stream_payload_bytes": stats["quic_stream_payload_total_bytes"],
            "stream_payload_multiplier": stats["quic_stream_payload_multiplier_after_repair"],
            "semantic_misses": stats["semantic_misses"],
            "repair_full_frames": stats["repair_full_frames"],
            "client_elapsed_ms": stats["client_elapsed_ms"],
            "reconstruction_ok": stats["reconstruction_ok"],
            "loss_every": stats["datagram_loss_every"],
        })
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    args.output_json.write_text(json.dumps({"results": results}, indent=2, sort_keys=True) + "\n")
    print(args.output_csv)


if __name__ == "__main__":
    main()
