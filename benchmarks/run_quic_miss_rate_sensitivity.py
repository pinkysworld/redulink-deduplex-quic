#!/usr/bin/env python3
"""Measure how batched semantic repairs change native QUIC stream bytes.

Each point uses the same deterministic warm/update pair and native aioquic
application-stream mapping. Only the receiver dictionary thinning interval is
changed. No completion-time or fairness claim is made.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototypes"))

from redulink_aioquic_experiment import demo_payload, run_async  # type: ignore


async def run_point(*, missing_every: int, blocks: int) -> dict[str, Any]:
    warm, data = demo_payload(blocks)
    stats = await run_async(
        warm=warm,
        data=data,
        chunk_size=1024,
        missing_every=missing_every,
        wire_format="binary",
        loss_every=0,
    )
    ref_frames = int(stats["client_ref_frames_initial"])
    misses = int(stats["semantic_misses"])
    return {
        "missing_every": missing_every,
        "input_bytes": int(stats["input_bytes"]),
        "initial_ref_frames": ref_frames,
        "semantic_misses": misses,
        "miss_fraction": round(misses / ref_frames, 6) if ref_frames else 0.0,
        "forward_protocol_stream_bytes": int(stats["forward_protocol_stream_bytes"]),
        "reverse_repair_control_stream_bytes": int(stats["reverse_repair_control_stream_bytes"]),
        "protocol_stream_bytes": int(stats["protocol_stream_payload_total_bytes_excluding_diagnostics"]),
        "protocol_stream_multiplier": float(stats["quic_stream_payload_multiplier_after_repair"]),
        "reconstruction_ok": bool(stats["reconstruction_ok"]),
        "tls_server_certificate_verified": bool(stats["tls_server_certificate_verified"]),
        "tls_client_certificate_used": bool(stats["tls_client_certificate_used"]),
        "redulink_key_derivation": str(stats["redulink_key_derivation"]),
        "tls_exporter_invocation": str(stats["tls_exporter_invocation"]),
        "record_mac_transcript": str(stats["record_mac_transcript"]),
        "chunk_size_bytes": int(stats["chunk_size_bytes"]),
        "sender_dictionary_budget_chunks": int(stats["sender_dictionary_budget_chunks"]),
        "receiver_dictionary_budget_chunks": int(stats["receiver_dictionary_budget_chunks"]),
    }


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    rows = [
        await run_point(missing_every=missing_every, blocks=args.blocks)
        for missing_every in args.missing_every
    ]
    rows.sort(key=lambda row: float(row["miss_fraction"]))
    return {
        "experiment": "native_quic_miss_byte_sensitivity",
        "accounting": (
            "QUIC application-stream protocol bytes; diagnostic STATS responses excluded; "
            "one deterministic byte-accounting run per point"
        ),
        "claim_scope": "semantic repair byte cost and exact reconstruction only; no latency or fairness inference",
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blocks", type=int, default=96)
    parser.add_argument("--missing-every", type=int, nargs="+", default=[0, 16, 8, 4, 2, 1])
    parser.add_argument("--output-json", type=Path, default=ROOT / "results" / "quic_miss_rate_sensitivity.json")
    parser.add_argument("--output-csv", type=Path, default=ROOT / "results" / "quic_miss_rate_sensitivity.csv")
    args = parser.parse_args()
    result = asyncio.run(main_async(args))
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with args.output_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(result["rows"][0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(result["rows"])
    print(args.output_csv)


if __name__ == "__main__":
    main()
