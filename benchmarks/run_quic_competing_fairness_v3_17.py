#!/usr/bin/env python3
"""Measure competing Reno QUIC flows over one Linux tc/netem bottleneck.

Each pair starts application transmission at an asyncio barrier after both
connections are established and ReduLink preparation is complete. Cases are
raw/raw, ReduLink/ReduLink, and a calibrated raw/ReduLink pair whose application
sizes are chosen to make encoded stream work similar. Jain's index is computed
over encoded application-stream goodput, not reconstructed bytes. Per-pair
qdisc deltas verify that both connections traversed the same kernel bottleneck.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import datetime, timezone
import json
import platform
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "prototypes"))

from run_linux_netem_quic_path import (  # type: ignore
    counter_delta,
    netem_context,
    qdisc_counters,
    setup_commands,
)
from run_quic_flow_comparison import run_raw_async  # type: ignore
from redulink_aioquic_experiment import demo_payload, run_async as run_redulink_async  # type: ignore
from stats_utils import bootstrap_ci, jain_fairness, mean, round_float, stdev  # type: ignore

CASES = ("raw-raw", "redulink-redulink", "raw-redulink")


async def run_case(
    *,
    case: str,
    round_id: int,
    raw_blocks: int,
    redulink_blocks: int,
    congestion_control_algorithm: str,
    device: str | None,
) -> dict[str, Any]:
    if case not in CASES:
        raise ValueError(f"unknown fairness case: {case}")
    _raw_warm, raw_data = demo_payload(raw_blocks)
    redulink_warm, redulink_data = demo_payload(redulink_blocks)
    barrier = asyncio.Barrier(2)

    def raw_factory() -> Awaitable[dict[str, Any]]:
        return run_raw_async(
            raw_data,
            congestion_control_algorithm=congestion_control_algorithm,
            start_barrier=barrier,
        )

    def redulink_factory() -> Awaitable[dict[str, Any]]:
        return run_redulink_async(
            warm=redulink_warm,
            data=redulink_data,
            chunk_size=1024,
            missing_every=0,
            wire_format="binary",
            sender_max_dict_chunks=max(8192, redulink_blocks + 256),
            receiver_max_dict_chunks=max(8192, redulink_blocks + 256),
            congestion_control_algorithm=congestion_control_algorithm,
            start_barrier=barrier,
        )

    factories: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {
        "raw": raw_factory,
        "redulink": redulink_factory,
    }
    flow_types = {
        "raw-raw": ("raw", "raw"),
        "redulink-redulink": ("redulink", "redulink"),
        "raw-redulink": ("raw", "redulink"),
    }[case]
    before = qdisc_counters(device)[0] if device is not None else None
    first, second = await asyncio.gather(
        factories[flow_types[0]](), factories[flow_types[1]](),
    )
    after = qdisc_counters(device)[0] if device is not None else None
    qdisc = counter_delta(before, after) if before is not None and after is not None else {
        "bytes": 0, "packets": 0, "drops": 0, "overlimits": 0, "requeues": 0,
    }
    rows = []
    for flow_name, method, stats in (
        ("A", flow_types[0], first),
        ("B", flow_types[1], second),
    ):
        completion_ms = float(stats["client_application_transfer_elapsed_ms"])
        encoded_bytes = int(stats["quic_stream_payload_total_bytes"])
        reconstructed_bytes = int(
            stats.get("server_reconstructed_bytes", stats.get("server_received_bytes", stats["input_bytes"])),
        )
        rows.append({
            "case": case,
            "round": round_id,
            "flow": flow_name,
            "method": method,
            "input_bytes": int(stats["input_bytes"]),
            "encoded_stream_payload_bytes": encoded_bytes,
            "reconstructed_bytes": reconstructed_bytes,
            "client_completion_ms": round(completion_ms, 3),
            "connection_plus_application_completion_ms": float(
                stats["client_network_elapsed_ms"],
            ),
            "client_ttfb_ms": float(
                stats["client_application_time_to_first_reconstructed_byte_ms"],
            ),
            "encoded_goodput_mbps": round(
                encoded_bytes * 8 / (completion_ms / 1000.0) / 1e6, 6,
            ),
            "reconstructed_goodput_mbps": round(
                reconstructed_bytes * 8 / (completion_ms / 1000.0) / 1e6, 6,
            ),
            "reconstruction_ok": bool(stats["reconstruction_ok"]),
            "congestion_control_algorithm": str(stats["congestion_control_algorithm"]),
            "application_stream_id": int(stats["application_stream_id"]),
        })
    encoded_rates = [float(row["encoded_goodput_mbps"]) for row in rows]
    reconstructed_rates = [float(row["reconstructed_goodput_mbps"]) for row in rows]
    encoded_work = [int(row["encoded_stream_payload_bytes"]) for row in rows]
    completion = [float(row["client_completion_ms"]) for row in rows]
    return {
        "case": case,
        "round": round_id,
        "flows": rows,
        "encoded_goodput_jain_fairness": round_float(jain_fairness(encoded_rates)),
        "reconstructed_goodput_jain_diagnostic": round_float(jain_fairness(reconstructed_rates)),
        "encoded_work_max_to_min_ratio": round_float(max(encoded_work) / min(encoded_work)),
        "completion_max_to_min_ratio": round_float(max(completion) / min(completion)),
        "pair_qdisc_bytes": qdisc["bytes"],
        "pair_qdisc_packets": qdisc["packets"],
        "pair_qdisc_drops": qdisc["drops"],
        "pair_qdisc_overlimits": qdisc["overlimits"],
        "pair_qdisc_requeues": qdisc["requeues"],
        "all_reconstructed": all(bool(row["reconstruction_ok"]) for row in rows),
    }


def summarize(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for case in CASES:
        selected = [pair for pair in pairs if pair["case"] == case]
        fairness = [float(pair["encoded_goodput_jain_fairness"]) for pair in selected]
        completion_skew = [float(pair["completion_max_to_min_ratio"]) for pair in selected]
        work_skew = [float(pair["encoded_work_max_to_min_ratio"]) for pair in selected]
        fairness_low, fairness_high = bootstrap_ci(fairness)
        completion_low, completion_high = bootstrap_ci(completion_skew)
        summaries.append({
            "case": case,
            "rounds": len(selected),
            "encoded_goodput_jain_fairness_mean": round_float(mean(fairness)),
            "encoded_goodput_jain_fairness_sd": round_float(stdev(fairness)),
            "encoded_goodput_jain_fairness_ci95_low": round_float(fairness_low),
            "encoded_goodput_jain_fairness_ci95_high": round_float(fairness_high),
            "completion_max_to_min_ratio_mean": round_float(mean(completion_skew)),
            "completion_max_to_min_ratio_ci95_low": round_float(completion_low),
            "completion_max_to_min_ratio_ci95_high": round_float(completion_high),
            "encoded_work_max_to_min_ratio_mean": round_float(mean(work_skew)),
            "qdisc_bytes_total": sum(int(pair["pair_qdisc_bytes"]) for pair in selected),
            "qdisc_packets_total": sum(int(pair["pair_qdisc_packets"]) for pair in selected),
            "qdisc_drops_total": sum(int(pair["pair_qdisc_drops"]) for pair in selected),
            "all_reconstructed": all(bool(pair["all_reconstructed"]) for pair in selected),
        })
    return summaries


async def run_experiment(
    *,
    rounds: int,
    raw_blocks: int,
    redulink_blocks: int,
    congestion_control_algorithm: str,
    device: str | None,
) -> dict[str, Any]:
    pairs = []
    for round_id in range(1, rounds + 1):
        rotation = (round_id - 1) % len(CASES)
        order = CASES[rotation:] + CASES[:rotation]
        for case in order:
            pair = await run_case(
                case=case,
                round_id=round_id,
                raw_blocks=raw_blocks,
                redulink_blocks=redulink_blocks,
                congestion_control_algorithm=congestion_control_algorithm,
                device=device,
            )
            pair["case_execution_order"] = order.index(case) + 1
            pairs.append(pair)
    return {
        "pairs": pairs,
        "summary": summarize(pairs),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--raw-blocks", type=int, default=814)
    parser.add_argument("--redulink-blocks", type=int, default=8192)
    parser.add_argument("--congestion-control", choices=["reno", "cubic"], default="reno")
    parser.add_argument("--rate-mbps", type=float, default=10.0)
    parser.add_argument("--rtt-ms", type=float, default=40.0)
    parser.add_argument("--loss-percent", type=float, default=0.5)
    parser.add_argument("--device", default="lo")
    parser.add_argument("--limit-packets", type=int, default=10000)
    parser.add_argument("--no-sudo", action="store_true")
    parser.add_argument("--unshaped-local", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--output-json", type=Path,
        default=ROOT / "results" / "quic_competing_fairness_v3_17.json",
    )
    parser.add_argument(
        "--output-csv", type=Path,
        default=ROOT / "results" / "quic_competing_fairness_v3_17.csv",
    )
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps({
            "experiment": "quic_competing_fairness_v3_17_dry_run",
            "setup": setup_commands(
                device=args.device,
                rate_mbps=args.rate_mbps,
                rtt_ms=args.rtt_ms,
                loss_percent=args.loss_percent,
                limit_packets=args.limit_packets,
                use_sudo=not args.no_sudo,
            ),
            "cases": CASES,
            "rounds": args.rounds,
        }, indent=2, sort_keys=True))
        return
    if not args.unshaped_local and platform.system() != "Linux":
        raise SystemExit("shaped fairness execution requires Linux; use --dry-run or --unshaped-local")

    qdisc_provenance: dict[str, Any] | None = None
    if args.unshaped_local:
        experiment = asyncio.run(run_experiment(
            rounds=args.rounds,
            raw_blocks=args.raw_blocks,
            redulink_blocks=args.redulink_blocks,
            congestion_control_algorithm=args.congestion_control,
            device=None,
        ))
    else:
        with netem_context(
            device=args.device,
            rate_mbps=args.rate_mbps,
            rtt_ms=args.rtt_ms,
            loss_percent=args.loss_percent,
            limit_packets=args.limit_packets,
            use_sudo=not args.no_sudo,
        ) as qdisc_provenance:
            experiment = asyncio.run(run_experiment(
                rounds=args.rounds,
                raw_blocks=args.raw_blocks,
                redulink_blocks=args.redulink_blocks,
                congestion_control_algorithm=args.congestion_control,
                device=args.device,
            ))
    import aioquic  # type: ignore

    result = {
        "experiment": "quic_competing_fairness_v3_17",
        "claim_scope": (
            "Jain fairness of encoded QUIC application-stream goodput for two synchronized connections "
            "sharing one Linux tc/netem bottleneck; the application timer starts after connection setup "
            "and ReduLink preparation so the barrier aligns first writes; connection-plus-preparation "
            "completion is retained separately; reconstructed-goodput fairness is diagnostic only"
        ),
        "parameters": {
            "rounds": args.rounds,
            "raw_blocks": args.raw_blocks,
            "redulink_blocks": args.redulink_blocks,
            "block_bytes": 1024,
            "rate_mbps": args.rate_mbps if not args.unshaped_local else None,
            "rtt_ms": args.rtt_ms if not args.unshaped_local else None,
            "loss_percent": args.loss_percent if not args.unshaped_local else None,
            "congestion_control_algorithm": args.congestion_control,
            "application_start_barrier": (
                "after both QUIC connections are established and all ReduLink frame and warm-"
                "dictionary preparation is complete; immediately before first stream writes"
            ),
            "goodput_timer": "application barrier release to exact transfer completion",
        },
        "provenance": {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(),
            "python": sys.version,
            "aioquic_version": aioquic.__version__,
            "qdisc": qdisc_provenance,
        },
        **experiment,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = [
        {**flow, **{
            "encoded_goodput_jain_fairness": pair["encoded_goodput_jain_fairness"],
            "pair_qdisc_bytes": pair["pair_qdisc_bytes"],
            "pair_qdisc_packets": pair["pair_qdisc_packets"],
            "pair_qdisc_drops": pair["pair_qdisc_drops"],
            "case_execution_order": pair["case_execution_order"],
        }}
        for pair in result["pairs"]
        for flow in pair["flows"]
    ]
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
