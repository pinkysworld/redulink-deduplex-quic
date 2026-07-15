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

DEFAULT_BLOCKS = [96, 512, 1024, 8192, 16384, 16384]
DEFAULT_ENDPOINT_BUDGETS = [8192, 8192, 8192, 8192, 8192, 24576]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--blocks", type=int, nargs="+", default=DEFAULT_BLOCKS)
    p.add_argument("--budgets", type=int, nargs="+", default=None,
                   help="matched sender/receiver dictionary budget per row; one value broadcasts")
    p.add_argument("--loss-every", type=int, default=0)
    p.add_argument("--output-csv", type=Path, default=ROOT / "results" / "aioquic_scaling_experiment.csv")
    p.add_argument("--output-json", type=Path, default=ROOT / "results" / "aioquic_scaling_experiment.json")
    args = p.parse_args()
    rows = []
    budgets = (
        list(DEFAULT_ENDPOINT_BUDGETS)
        if args.budgets is None and args.blocks == DEFAULT_BLOCKS
        else (args.budgets or [8192] * len(args.blocks))
    )
    if len(budgets) == 1:
        budgets = budgets * len(args.blocks)
    if len(budgets) != len(args.blocks):
        raise SystemExit("--budgets must match --blocks length (or be one value)")
    for blocks, budget in zip(args.blocks, budgets):
        stats = run_experiment(
            payload_blocks=blocks,
            missing_every=0,
            wire_format="binary",
            loss_every=args.loss_every,
            sender_max_dict_chunks=budget,
            receiver_max_dict_chunks=budget,
        )
        rows.append({
            "payload_blocks": blocks,
            "endpoint_dictionary_budget_chunks": budget,
            "sender_dictionary_budget_chunks": budget,
            "receiver_dictionary_budget_chunks": budget,
            "receiver_dictionary_thinning_every": 0,
            "chunk_size_bytes": stats["chunk_size_bytes"],
            "input_bytes": stats["input_bytes"],
            "stream_payload_bytes": stats["quic_stream_payload_total_bytes"],
            "forward_protocol_stream_bytes": stats["forward_protocol_stream_bytes"],
            "reverse_repair_control_stream_bytes": stats["reverse_repair_control_stream_bytes"],
            "diagnostic_stats_stream_bytes_excluded": stats["diagnostic_stats_stream_bytes"],
            "stream_payload_multiplier": stats["quic_stream_payload_multiplier_after_repair"],
            "semantic_misses": stats["semantic_misses"],
            "repair_full_frames": stats["repair_full_frames"],
            "reconstruction_ok": stats["reconstruction_ok"],
            "application_stream_id": stats["application_stream_id"],
            "loss_every": stats["datagram_loss_every"],
            "tls_server_certificate_verified": stats["tls_server_certificate_verified"],
            "tls_client_certificate_used": stats["tls_client_certificate_used"],
            "redulink_key_derivation": stats["redulink_key_derivation"],
            "tls_exporter_invocation": stats["tls_exporter_invocation"],
            "record_mac_transcript": stats["record_mac_transcript"],
            "dictionary_policy": "matched endpoint bounded true LRU; successful REF hits refresh recency",
        })
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    args.output_json.write_text(json.dumps({"results": rows}, indent=2, sort_keys=True) + "\n")
    print(args.output_csv)


if __name__ == "__main__":
    main()
