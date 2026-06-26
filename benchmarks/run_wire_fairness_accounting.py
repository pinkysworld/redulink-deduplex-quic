#!/usr/bin/env python3
"""Deterministic wire-byte fairness accounting experiment.

This experiment is intentionally not a transport simulator. It checks the
accounting rule that ReduLink competes on encoded wire bytes rather than
reconstructed bytes. A bottleneck scheduler alternates service between a
ReduLink-encoded flow and a raw competitor flow. ReduLink may deliver more
application bytes per transmitted byte, but the bottleneck service share is
computed from bytes placed on the wire.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "prototypes"))

import redulink_model as redulink
from redulink_udp_repair_experiment import demo_payload


def packetize_redulink(data: bytes, warm: bytes, *, chunk_size: int) -> tuple[list[int], int, int, int]:
    frames, stats = redulink.encode(data, chunker="fixed", chunk_size=chunk_size, warm_dictionary=warm)
    wire_packets = []
    for fr in frames:
        if fr.kind == "FULL":
            wire_packets.append(redulink.FULL_OVERHEAD + len(fr.payload))
        else:
            wire_packets.append(redulink.REF_OVERHEAD)
    return wire_packets, len(data), stats.wire_bytes, stats.ref_frames


def packetize_raw(data: bytes, *, mtu_payload: int) -> list[int]:
    packets = []
    for i in range(0, len(data), mtu_payload):
        packets.append(min(mtu_payload, len(data) - i) + 28)  # UDP/IP header approximation
    return packets


def round_robin_service(redulink_packets: list[int], raw_packets: list[int], *, budget_per_round: int = 4096) -> dict[str, float]:
    queues = {"redulink": list(redulink_packets), "raw": list(raw_packets)}
    sent = {"redulink": 0, "raw": 0}
    rounds = 0
    while queues["redulink"] or queues["raw"]:
        rounds += 1
        for name in ("redulink", "raw"):
            budget = budget_per_round
            q = queues[name]
            while q and q[0] <= budget:
                size = q.pop(0)
                sent[name] += size
                budget -= size
            # If a single packet exceeds the budget, transmit one packet and
            # account the overrun. This keeps the scheduler total-order simple.
            if q and sent[name] == 0:
                sent[name] += q.pop(0)
    total = sent["redulink"] + sent["raw"]
    return {
        "rounds": rounds,
        "redulink_wire_bytes": sent["redulink"],
        "raw_wire_bytes": sent["raw"],
        "redulink_wire_share": sent["redulink"] / total if total else 0.0,
        "raw_wire_share": sent["raw"] / total if total else 0.0,
    }


def run_experiment() -> dict[str, float | int | bool | str]:
    warm, data = demo_payload()
    redulink_packets, reconstructed, model_wire, refs = packetize_redulink(data, warm, chunk_size=1024)
    raw_packets = packetize_raw(data, mtu_payload=1024)
    sched = round_robin_service(redulink_packets, raw_packets)
    result = {
        "experiment": "wire_byte_fairness_accounting",
        "reconstructed_bytes_redulink": reconstructed,
        "application_bytes_raw": len(data),
        "redulink_model_wire_bytes": model_wire,
        "raw_wire_bytes_without_scheduler": sum(raw_packets),
        "redulink_ref_frames": refs,
        "redulink_effective_app_multiplier": round(reconstructed / model_wire, 6),
        "wire_share_redulink": round(sched["redulink_wire_share"], 6),
        "wire_share_raw": round(sched["raw_wire_share"], 6),
        "redulink_uses_less_wire_than_raw": model_wire < sum(raw_packets),
        "fairness_rule": "bottleneck service and congestion accounting use encoded wire bytes, not reconstructed bytes",
    }
    result.update({k: int(v) if k.endswith("bytes") or k == "rounds" else v for k, v in sched.items()})
    return result


def main() -> None:
    out_json = ROOT / "results" / "wire_fairness_accounting.json"
    out_csv = ROOT / "results" / "wire_fairness_accounting.csv"
    result = run_experiment()
    out_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(result.keys()))
        writer.writeheader()
        writer.writerow(result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
