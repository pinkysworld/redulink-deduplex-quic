#!/usr/bin/env python3
"""Compare raw and ReduLink bytes at one QUIC application-stream layer.

The input is the zero-loss native aioquic flow-comparison result. Diagnostic
STATS responses are excluded for both methods. This is an accounting check,
not a congestion-control or competing-flow fairness experiment.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def summarize(raw: dict[str, str], redulink: dict[str, str]) -> dict[str, object]:
    raw_input = int(raw["input_bytes"])
    redulink_input = int(redulink["input_bytes"])
    if raw_input != redulink_input:
        raise ValueError("raw and ReduLink rows must reconstruct the same byte count")
    if raw.get("reconstruction_ok") != "True" or redulink.get("reconstruction_ok") != "True":
        raise ValueError("both zero-loss rows must report exact reconstruction")

    raw_bytes = int(raw["stream_payload_bytes"])
    redulink_bytes = int(redulink["stream_payload_bytes"])
    redulink_forward = int(redulink["forward_protocol_stream_bytes"])
    redulink_reverse = int(redulink["reverse_repair_control_stream_bytes"])
    if redulink_bytes != redulink_forward + redulink_reverse:
        raise ValueError("ReduLink directional byte accounting is inconsistent")
    if raw_bytes != int(raw["forward_protocol_stream_bytes"]):
        raise ValueError("raw forward and total protocol bytes must match")

    combined = raw_bytes + redulink_bytes
    return {
        "experiment": "protocol_stream_byte_accounting",
        "accounting_layer": "QUIC application-stream payload bytes, excluding diagnostic STATS responses",
        "input_bytes_per_method": raw_input,
        "raw_protocol_stream_bytes": raw_bytes,
        "redulink_forward_protocol_stream_bytes": redulink_forward,
        "redulink_reverse_repair_control_stream_bytes": redulink_reverse,
        "redulink_protocol_stream_bytes": redulink_bytes,
        "raw_diagnostic_stats_stream_bytes_excluded": int(raw["diagnostic_stats_stream_bytes"]),
        "redulink_diagnostic_stats_stream_bytes_excluded": int(redulink["diagnostic_stats_stream_bytes"]),
        "raw_protocol_multiplier": round(raw_input / raw_bytes, 6) if raw_bytes else 0.0,
        "redulink_protocol_multiplier": round(raw_input / redulink_bytes, 6) if redulink_bytes else 0.0,
        "raw_byte_share_in_pair": round(raw_bytes / combined, 6) if combined else 0.0,
        "redulink_byte_share_in_pair": round(redulink_bytes / combined, 6) if combined else 0.0,
        "redulink_uses_fewer_protocol_stream_bytes": redulink_bytes < raw_bytes,
        "claim_scope": (
            "same-layer byte accounting for one deterministic localhost workload; "
            "does not establish congestion-control fairness or latency"
        ),
    }


def run_experiment(source_csv: Path = ROOT / "results" / "quic_flow_comparison.csv") -> dict[str, object]:
    with source_csv.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    zero_loss = {row["method"]: row for row in rows if int(row["loss_every"]) == 0}
    required = {"raw-quic-stream", "redulink-binary-quic-stream"}
    if set(zero_loss) != required:
        raise ValueError(f"expected exactly the zero-loss methods {sorted(required)}")
    return summarize(zero_loss["raw-quic-stream"], zero_loss["redulink-binary-quic-stream"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, default=ROOT / "results" / "quic_flow_comparison.csv")
    parser.add_argument("--output-json", type=Path, default=ROOT / "results" / "protocol_stream_byte_accounting.json")
    parser.add_argument("--output-csv", type=Path, default=ROOT / "results" / "protocol_stream_byte_accounting.csv")
    args = parser.parse_args()
    result = run_experiment(args.source_csv)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with args.output_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(result.keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerow(result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
