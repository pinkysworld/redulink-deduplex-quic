#!/usr/bin/env python3
"""Summarize repeated QUIC evidence with deterministic bootstrap intervals."""
from __future__ import annotations

import csv
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from stats_utils import bootstrap_ci, mean, round_float, stdev  # type: ignore


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def metric_row(*, experiment: str, scenario: str, metric: str, values: Iterable[float]) -> dict[str, Any]:
    vals = [float(v) for v in values]
    lo, hi = bootstrap_ci(vals)
    return {
        "experiment": experiment,
        "scenario": scenario,
        "metric": metric,
        "n": len(vals),
        "mean": round_float(mean(vals)),
        "stdev": round_float(stdev(vals)),
        "ci95_low": round_float(lo),
        "ci95_high": round_float(hi),
        "min": round_float(min(vals) if vals else 0.0),
        "max": round_float(max(vals) if vals else 0.0),
    }


def emulated_path_rows(path: Path, *, experiment: str = "quic_emulated_path") -> list[dict[str, Any]]:
    rows = read_csv(path)
    grouped: dict[tuple[str, str, str, str, str], dict[str, dict[str, str]]] = {}
    for row in rows:
        key = (row["payload"], row["rate_mbps"], row["rtt_ms"], row["loss_every"], row["round"])
        grouped.setdefault(key, {})[row["method"]] = row

    out = []
    by_scenario: dict[str, dict[str, list[float]]] = {}
    for (payload, rate, rtt, loss, _round), pair in grouped.items():
        if "raw-quic-stream" not in pair or "redulink-binary-quic-stream" not in pair:
            continue
        raw = pair["raw-quic-stream"]
        rl = pair["redulink-binary-quic-stream"]
        scenario = f"{payload}; rate={rate}Mbps; rtt={rtt}ms; loss_every={loss}"
        bucket = by_scenario.setdefault(scenario, {
            "completion_ratio_redulink_over_raw": [],
            "encoded_byte_ratio_redulink_over_raw": [],
            "redulink_stream_multiplier": [],
        })
        raw_ms = float(raw["completion_ms_measured"])
        rl_ms = float(rl["completion_ms_measured"])
        raw_encoded = float(raw["encoded_stream_payload_bytes"])
        rl_encoded = float(rl["encoded_stream_payload_bytes"])
        bucket["completion_ratio_redulink_over_raw"].append(rl_ms / raw_ms)
        bucket["encoded_byte_ratio_redulink_over_raw"].append(rl_encoded / raw_encoded)
        bucket["redulink_stream_multiplier"].append(float(rl["reconstructed_bytes"]) / rl_encoded)

    for scenario, metrics in sorted(by_scenario.items()):
        for metric, values in metrics.items():
            out.append(metric_row(
                experiment=experiment,
                scenario=scenario,
                metric=metric,
                values=values,
            ))
    return out


def competing_flow_rows(path: Path) -> list[dict[str, Any]]:
    rows = read_csv(path)
    grouped: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        match = re.search(r"concurrent round (\d+)", row.get("note", ""))
        key = match.group(1) if match else row.get("note", "")
        grouped.setdefault(key, {})[row["method"]] = row

    metrics = {
        "completion_ratio_redulink_over_raw": [],
        "encoded_byte_ratio_redulink_over_raw": [],
        "redulink_stream_multiplier": [],
    }
    for pair in grouped.values():
        if "raw-quic-stream" not in pair or "redulink-binary-quic-stream" not in pair:
            continue
        raw = pair["raw-quic-stream"]
        rl = pair["redulink-binary-quic-stream"]
        metrics["completion_ratio_redulink_over_raw"].append(float(rl["elapsed_ms"]) / float(raw["elapsed_ms"]))
        metrics["encoded_byte_ratio_redulink_over_raw"].append(
            float(rl["encoded_stream_payload_bytes"]) / float(raw["encoded_stream_payload_bytes"])
        )
        metrics["redulink_stream_multiplier"].append(float(rl["effective_multiplier"]))

    return [
        metric_row(
            experiment="quic_competing_flows",
            scenario="localhost concurrent aioquic pair; rate_hint=25Mbps",
            metric=metric,
            values=values,
        )
        for metric, values in metrics.items()
    ]


def repeated_trial_rows(path: Path) -> list[dict[str, Any]]:
    rows = read_csv(path)
    metrics = {
        "redulink_stream_multiplier": [float(r["redulink_stream_multiplier"]) for r in rows],
        "redulink_udp_est_multiplier": [float(r["redulink_udp_est_multiplier"]) for r in rows],
        "completion_ratio_redulink_over_raw": [
            float(r["redulink_client_ms"]) / float(r["raw_client_ms"]) for r in rows
        ],
    }
    return [
        metric_row(
            experiment="repeated_quic_trials",
            scenario="native aioquic sequential smoke repeats",
            metric=metric,
            values=values,
        )
        for metric, values in metrics.items()
    ]


def main() -> None:
    rows = []
    rows.extend(emulated_path_rows(ROOT / "results" / "quic_emulated_path.csv"))
    redis_path = ROOT / "results" / "quic_emulated_path_redis.csv"
    if redis_path.exists():
        rows.extend(emulated_path_rows(redis_path, experiment="quic_emulated_path_redis"))
    rows.extend(competing_flow_rows(ROOT / "results" / "quic_competing_flows.csv"))
    rows.extend(repeated_trial_rows(ROOT / "results" / "repeated_quic_trials.csv"))
    out_csv = ROOT / "results" / "quic_statistical_evidence.csv"
    out_json = ROOT / "results" / "quic_statistical_evidence.json"
    write_csv(out_csv, rows)
    out_json.write_text(json.dumps({
        "experiment": "quic_statistical_evidence",
        "note": "Deterministic percentile bootstrap confidence intervals over paired repeated local QUIC measurements.",
        "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")
    print(out_csv)


if __name__ == "__main__":
    main()
