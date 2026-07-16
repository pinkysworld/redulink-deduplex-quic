#!/usr/bin/env python3
"""Measure raw and ReduLink QUIC transfers over a Linux tc/netem kernel path.

The harness runs paired, order-alternated transfers in an otherwise isolated
network namespace. It reports client-clock completion and first-byte times,
combined endpoint process CPU, exact reconstruction, application-stream bytes,
and per-transfer Linux qdisc packet/byte counter deltas. It never subtracts
timestamps obtained from different endpoint clocks.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "prototypes"))

from stats_utils import bootstrap_ci, mean, round_float, stdev  # type: ignore

COUNTER_NAMES = ("bytes", "packets", "drops", "overlimits", "requeues")


def _fmt_float(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _prefix(use_sudo: bool) -> list[str]:
    return ["sudo"] if use_sudo else []


def setup_commands(
    *,
    device: str,
    rate_mbps: float,
    rtt_ms: float,
    loss_percent: float,
    limit_packets: int,
    use_sudo: bool = True,
) -> list[list[str]]:
    if rate_mbps <= 0 or rtt_ms < 0 or not 0 <= loss_percent < 100:
        raise ValueError("rate must be positive, RTT non-negative, and loss in [0, 100)")
    command = [
        *_prefix(use_sudo),
        "tc", "qdisc", "replace", "dev", device, "root",
        "netem", "delay", f"{_fmt_float(rtt_ms / 2.0)}ms",
        "rate", f"{_fmt_float(rate_mbps)}mbit",
        "limit", str(limit_packets),
    ]
    if loss_percent:
        command.extend(["loss", f"{_fmt_float(loss_percent)}%"])
    return [command]


def cleanup_commands(*, device: str, use_sudo: bool = True) -> list[list[str]]:
    return [[*_prefix(use_sudo), "tc", "qdisc", "del", "dev", device, "root"]]


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, text=True, capture_output=True)


def _counter_value(mapping: Any, name: str) -> int:
    if not isinstance(mapping, dict):
        return 0
    direct = mapping.get(name)
    if isinstance(direct, (int, float)):
        return int(direct)
    for key in ("stats", "stats2", "basic"):
        nested = mapping.get(key)
        value = _counter_value(nested, name)
        if value:
            return value
    return 0


def parse_qdisc_counters(payload: str) -> dict[str, int]:
    records = json.loads(payload)
    if not isinstance(records, list) or not records:
        raise ValueError("tc returned no qdisc records")
    root_records = [record for record in records if isinstance(record, dict) and record.get("root")]
    candidates = root_records or [record for record in records if isinstance(record, dict)]
    record = next((item for item in candidates if item.get("kind") == "netem"), candidates[0])
    return {name: _counter_value(record, name) for name in COUNTER_NAMES}


def qdisc_counters(device: str) -> tuple[dict[str, int], str]:
    proc = _run(["tc", "-j", "-s", "qdisc", "show", "dev", device])
    return parse_qdisc_counters(proc.stdout), proc.stdout.strip()


def counter_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {
        name: max(0, int(after.get(name, 0)) - int(before.get(name, 0)))
        for name in COUNTER_NAMES
    }


@contextmanager
def netem_context(
    *,
    device: str,
    rate_mbps: float,
    rtt_ms: float,
    loss_percent: float,
    limit_packets: int,
    use_sudo: bool,
) -> Any:
    for command in setup_commands(
        device=device,
        rate_mbps=rate_mbps,
        rtt_ms=rtt_ms,
        loss_percent=loss_percent,
        limit_packets=limit_packets,
        use_sudo=use_sudo,
    ):
        _run(command)
    state: dict[str, Any] = {}
    try:
        before, raw_before = qdisc_counters(device)
        state.update({"counters_before": before, "qdisc_json_before": raw_before})
        yield state
    finally:
        try:
            after, raw_after = qdisc_counters(device)
            state.update({"counters_after": after, "qdisc_json_after": raw_after})
        except Exception as exc:  # cleanup must still run
            state["counter_capture_after_error"] = str(exc)
        failures = []
        for command in cleanup_commands(device=device, use_sudo=use_sudo):
            proc = _run(command, check=False)
            if proc.returncode != 0:
                failures.append({"command": command, "stderr": proc.stderr.strip()})
        if failures:
            print(f"WARNING: tc/netem cleanup failures: {failures}", file=sys.stderr)


def load_payload(kind: str) -> tuple[bytes, bytes, str]:
    if kind == "redis":
        base = ROOT / "data" / "external_positive_corpora" / "redis-layered-public-positive"
        return (
            (base / "warm.bin").read_bytes(),
            (base / "update.bin").read_bytes(),
            "hash-pinned public Redis release-layer bytes",
        )
    from redulink_aioquic_experiment import demo_payload  # type: ignore

    warm, update = demo_payload()
    return warm, update, "constructed deterministic warm-update control"


def row_from_stats(
    *,
    payload: str,
    payload_note: str,
    round_id: int,
    execution_order: int,
    method: str,
    stats: dict[str, Any],
    qdisc_delta: dict[str, int],
) -> dict[str, Any]:
    completion_ms = float(stats["client_network_elapsed_ms"])
    input_bytes = int(stats["input_bytes"])
    encoded_bytes = int(stats["quic_stream_payload_total_bytes"])
    reconstructed_bytes = int(
        stats.get("server_reconstructed_bytes", stats.get("server_received_bytes", input_bytes)),
    )
    return {
        "payload": payload,
        "payload_note": payload_note,
        "round": round_id,
        "execution_order": execution_order,
        "method": method,
        "input_bytes": input_bytes,
        "encoded_stream_payload_bytes": encoded_bytes,
        "reconstructed_bytes": reconstructed_bytes,
        "client_completion_ms": round(completion_ms, 3),
        "client_ttfb_ms": round(float(stats["client_time_to_first_reconstructed_byte_ms"]), 3),
        "server_completion_ms": round(float(stats["server_completion_ms"]), 3),
        "combined_endpoint_process_cpu_ms": round(
            float(stats["combined_endpoint_process_cpu_ms"]), 3,
        ),
        "reconstructed_goodput_mbps": round(
            reconstructed_bytes * 8 / (completion_ms / 1000.0) / 1e6, 6,
        ) if completion_ms else 0.0,
        "encoded_goodput_mbps": round(
            encoded_bytes * 8 / (completion_ms / 1000.0) / 1e6, 6,
        ) if completion_ms else 0.0,
        "qdisc_bytes": qdisc_delta["bytes"],
        "qdisc_packets": qdisc_delta["packets"],
        "qdisc_drops": qdisc_delta["drops"],
        "qdisc_overlimits": qdisc_delta["overlimits"],
        "qdisc_requeues": qdisc_delta["requeues"],
        "reconstruction_ok": bool(stats["reconstruction_ok"]),
        "semantic_misses": int(stats.get("semantic_misses", 0)),
        "repair_full_frames": int(stats.get("repair_full_frames", 0)),
        "measurement_control_stream_bytes_excluded": int(
            stats.get("measurement_control_stream_bytes_excluded", 0),
        ),
        "congestion_control_algorithm": str(stats["congestion_control_algorithm"]),
        "emulation": "Linux tc/netem qdisc on loopback in an isolated network namespace",
    }


async def measure_transfer(
    factory: Callable[[], Awaitable[dict[str, Any]]],
    *,
    device: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    before, _ = qdisc_counters(device)
    stats = await factory()
    after, _ = qdisc_counters(device)
    return stats, counter_delta(before, after)


async def run_round(
    *,
    payload: str,
    round_id: int,
    device: str,
    congestion_control_algorithm: str,
) -> list[dict[str, Any]]:
    from run_quic_flow_comparison import run_raw_async  # type: ignore
    from redulink_aioquic_experiment import run_async as run_redulink_async  # type: ignore

    warm, data, payload_note = load_payload(payload)

    async def raw() -> dict[str, Any]:
        return await run_raw_async(
            data,
            congestion_control_algorithm=congestion_control_algorithm,
        )

    async def redulink() -> dict[str, Any]:
        return await run_redulink_async(
            warm=warm,
            data=data,
            chunk_size=1024,
            missing_every=7,
            wire_format="binary",
            loss_every=0,
            congestion_control_algorithm=congestion_control_algorithm,
        )

    methods: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {
        "raw-quic-stream": raw,
        "redulink-binary-quic-stream": redulink,
    }
    order = (
        ["raw-quic-stream", "redulink-binary-quic-stream"]
        if round_id % 2
        else ["redulink-binary-quic-stream", "raw-quic-stream"]
    )
    rows = []
    for execution_order, method in enumerate(order, start=1):
        stats, counters = await measure_transfer(methods[method], device=device)
        rows.append(row_from_stats(
            payload=payload,
            payload_note=payload_note,
            round_id=round_id,
            execution_order=execution_order,
            method=method,
            stats=stats,
            qdisc_delta=counters,
        ))
    return rows


def _ratio_summary(prefix: str, values: list[float]) -> dict[str, Any]:
    low, high = bootstrap_ci(values)
    return {
        f"{prefix}_ratio_mean": round_float(mean(values)),
        f"{prefix}_ratio_sd": round_float(stdev(values)),
        f"{prefix}_ratio_ci95_low": round_float(low),
        f"{prefix}_ratio_ci95_high": round_float(high),
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, float, float, float], dict[int, dict[str, dict[str, Any]]]] = {}
    for row in rows:
        key = (row["payload"], row["rate_mbps"], row["rtt_ms"], row["loss_percent"])
        grouped.setdefault(key, {}).setdefault(int(row["round"]), {})[row["method"]] = row

    summaries = []
    metrics = {
        "client_completion": "client_completion_ms",
        "client_ttfb": "client_ttfb_ms",
        "server_completion": "server_completion_ms",
        "process_cpu": "combined_endpoint_process_cpu_ms",
        "stream_bytes": "encoded_stream_payload_bytes",
        "qdisc_bytes": "qdisc_bytes",
        "qdisc_packets": "qdisc_packets",
    }
    for (payload, rate, rtt, loss), rounds in sorted(grouped.items()):
        ratios: dict[str, list[float]] = {name: [] for name in metrics}
        paired_rows = []
        for pair in rounds.values():
            raw = pair.get("raw-quic-stream")
            redulink = pair.get("redulink-binary-quic-stream")
            if raw is None or redulink is None:
                continue
            paired_rows.extend([raw, redulink])
            for name, field in metrics.items():
                denominator = float(raw[field])
                if denominator > 0:
                    ratios[name].append(float(redulink[field]) / denominator)
        if not paired_rows:
            continue
        summary: dict[str, Any] = {
            "payload": payload,
            "rate_mbps": rate,
            "rtt_ms": rtt,
            "loss_percent": loss,
            "paired_rounds": len(ratios["client_completion"]),
            "all_reconstructed": all(bool(row["reconstruction_ok"]) for row in paired_rows),
            "congestion_control_algorithm": paired_rows[0]["congestion_control_algorithm"],
            "ratio_definition": "paired ReduLink value divided by paired raw-QUIC value",
        }
        for name, values in ratios.items():
            summary.update(_ratio_summary(name, values))
        summaries.append(summary)
    return summaries


def scenario_grid(args: argparse.Namespace) -> list[dict[str, Any]]:
    return [
        {"payload": payload, "rate_mbps": rate, "rtt_ms": rtt, "loss_percent": loss}
        for payload in args.payload
        for rate in args.rate_mbps
        for rtt in args.rtt_ms
        for loss in args.loss_percent
    ]


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    qdisc_configurations: list[dict[str, Any]] = []
    for scenario in scenario_grid(args):
        with netem_context(
            device=args.device,
            rate_mbps=scenario["rate_mbps"],
            rtt_ms=scenario["rtt_ms"],
            loss_percent=scenario["loss_percent"],
            limit_packets=args.limit_packets,
            use_sudo=not args.no_sudo,
        ) as qdisc_state:
            for round_id in range(1, args.rounds + 1):
                round_rows = await run_round(
                    payload=scenario["payload"],
                    round_id=round_id,
                    device=args.device,
                    congestion_control_algorithm=args.congestion_control,
                )
                for row in round_rows:
                    row.update(scenario)
                rows.extend(round_rows)
        qdisc_configurations.append({**scenario, **qdisc_state})

    tc_version = _run(["tc", "-V"], check=False)
    git_commit = _run(["git", "rev-parse", "HEAD"], check=False)
    import aioquic  # type: ignore

    return {
        "experiment": "linux_netem_quic_path_v3_17",
        "measurement_scope": (
            "isolated Linux loopback kernel path with tc/netem; paired order-alternated trials; "
            "client-clock completion and FIRST_BYTE acknowledgement timing; server-clock processing "
            "timing; combined in-process endpoint CPU; per-transfer root-qdisc byte and packet deltas"
        ),
        "clock_rule": "no timestamp subtraction across endpoint clocks",
        "packet_accounting": (
            "tc -j -s root-qdisc counter delta around each isolated transfer; includes QUIC handshake, "
            "encrypted packets, acknowledgements, close traffic observed before helper return, and the "
            "13-byte symmetric FIRST_BYTE measurement message"
        ),
        "provenance": {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "command": [sys.executable, *sys.argv],
            "platform": platform.platform(),
            "python": sys.version,
            "aioquic_version": aioquic.__version__,
            "tc_version": (tc_version.stdout or tc_version.stderr).strip(),
            "git_commit": git_commit.stdout.strip() if git_commit.returncode == 0 else "unavailable",
            "device": args.device,
            "qdisc_configurations": qdisc_configurations,
        },
        "rows": rows,
        "summary": summarize(rows),
    }


def write_outputs(
    result: dict[str, Any],
    *,
    output_json: Path,
    output_csv: Path,
    output_summary_csv: Path,
) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["rows"]:
        with output_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(result["rows"][0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(result["rows"])
    if result["summary"]:
        with output_summary_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(result["summary"][0]), lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(result["summary"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", choices=["demo", "redis"], nargs="+", default=["demo", "redis"])
    parser.add_argument("--rate-mbps", type=float, nargs="+", default=[5.0, 20.0])
    parser.add_argument("--rtt-ms", type=float, nargs="+", default=[20.0, 80.0])
    parser.add_argument("--loss-percent", type=float, nargs="+", default=[0.0, 0.5])
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--congestion-control", choices=["reno", "cubic"], default="reno")
    parser.add_argument("--device", default="lo")
    parser.add_argument("--limit-packets", type=int, default=10000)
    parser.add_argument("--no-sudo", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--output-json", type=Path, default=ROOT / "results" / "linux_netem_quic_path_v3_17.json",
    )
    parser.add_argument(
        "--output-csv", type=Path, default=ROOT / "results" / "linux_netem_quic_path_v3_17.csv",
    )
    parser.add_argument(
        "--output-summary-csv", type=Path,
        default=ROOT / "results" / "linux_netem_quic_path_v3_17_summary.csv",
    )
    args = parser.parse_args()
    if args.rounds < 1:
        raise SystemExit("--rounds must be positive")

    scenarios = scenario_grid(args)
    if args.dry_run:
        print(json.dumps({
            "experiment": "linux_netem_quic_path_v3_17_dry_run",
            "platform": platform.system(),
            "scenarios": scenarios,
            "setup": [
                setup_commands(
                    device=args.device,
                    rate_mbps=scenario["rate_mbps"],
                    rtt_ms=scenario["rtt_ms"],
                    loss_percent=scenario["loss_percent"],
                    limit_packets=args.limit_packets,
                    use_sudo=not args.no_sudo,
                )[0]
                for scenario in scenarios
            ],
            "cleanup": cleanup_commands(device=args.device, use_sudo=not args.no_sudo),
        }, indent=2, sort_keys=True))
        return
    if platform.system() != "Linux":
        raise SystemExit("Live tc/netem execution requires Linux; use --dry-run elsewhere.")

    result = asyncio.run(main_async(args))
    write_outputs(
        result,
        output_json=args.output_json,
        output_csv=args.output_csv,
        output_summary_csv=args.output_summary_csv,
    )
    print(json.dumps({
        "experiment": result["experiment"],
        "raw_rows": len(result["rows"]),
        "summary_rows": len(result["summary"]),
        "output_json": str(args.output_json),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
