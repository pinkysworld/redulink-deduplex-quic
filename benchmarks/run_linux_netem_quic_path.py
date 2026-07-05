#!/usr/bin/env python3
"""Run native aioquic raw vs ReduLink transfers over Linux tc/netem.

This is the Linux counterpart to the macOS pf/dnctl harness. It applies a
temporary netem qdisc to the loopback device, runs paired raw and ReduLink
aioquic transfers, writes CSV/JSON evidence, and always attempts qdisc cleanup.

The live sweep requires Linux, root privileges (or sudo), and iproute2 `tc`.
Use `--dry-run` first to inspect the exact commands without changing networking.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import platform
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "prototypes"))

from stats_utils import bootstrap_ci, mean, round_float, stdev  # type: ignore


def _fmt_float(value: float) -> str:
    text = f"{value:.3f}"
    return text.rstrip("0").rstrip(".")


def _prefix(use_sudo: bool) -> list[str]:
    return ["sudo"] if use_sudo else []


def setup_commands(*, device: str, rate_mbps: float, rtt_ms: float,
                   loss_percent: float, limit_packets: int,
                   use_sudo: bool = True) -> list[list[str]]:
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


@contextmanager
def netem_context(*, device: str, rate_mbps: float, rtt_ms: float,
                  loss_percent: float, limit_packets: int, use_sudo: bool) -> Any:
    for command in setup_commands(
        device=device,
        rate_mbps=rate_mbps,
        rtt_ms=rtt_ms,
        loss_percent=loss_percent,
        limit_packets=limit_packets,
        use_sudo=use_sudo,
    ):
        _run(command)
    try:
        yield
    finally:
        failures = []
        for command in cleanup_commands(device=device, use_sudo=use_sudo):
            proc = _run(command, check=False)
            if proc.returncode not in (0,):
                failures.append({"command": command, "stderr": proc.stderr.strip()})
        if failures:
            print(f"WARNING: tc/netem cleanup failures: {failures}", file=sys.stderr)


def _load_payload(kind: str) -> tuple[bytes, bytes, str]:
    if kind == "redis":
        base = ROOT / "data" / "external_positive_corpora" / "redis-layered-public-positive"
        warm = (base / "warm.bin").read_bytes()
        update = (base / "update.bin").read_bytes()
        return warm, update, "real Redis-layered public bytes"
    from redulink_aioquic_experiment import demo_payload  # type: ignore
    warm, update = demo_payload()
    return warm, update, "constructed byte-stable demo"


async def run_round(*, payload: str, round_id: int) -> list[dict[str, Any]]:
    from run_quic_flow_comparison import run_raw_async  # type: ignore
    from redulink_aioquic_experiment import run_async as run_redulink_async  # type: ignore

    warm, data, payload_note = _load_payload(payload)
    raw_task = asyncio.create_task(run_raw_async(data, loss_every=0))
    rl_task = asyncio.create_task(run_redulink_async(
        warm=warm,
        data=data,
        chunk_size=1024,
        missing_every=7,
        wire_format="binary",
        loss_every=0,
    ))
    raw, rl = await asyncio.gather(raw_task, rl_task)
    return [
        row_from_stats(payload=payload, payload_note=payload_note, round_id=round_id,
                       method="raw-quic-stream", stats=raw,
                       encoded_key="quic_stream_payload_total_bytes",
                       reconstructed_key="server_received_bytes"),
        row_from_stats(payload=payload, payload_note=payload_note, round_id=round_id,
                       method="redulink-binary-quic-stream", stats=rl,
                       encoded_key="quic_stream_payload_total_bytes",
                       reconstructed_key="server_reconstructed_bytes"),
    ]


def row_from_stats(*, payload: str, payload_note: str, round_id: int, method: str,
                   stats: dict[str, Any], encoded_key: str,
                   reconstructed_key: str) -> dict[str, Any]:
    elapsed = float(stats.get("client_elapsed_ms", 0.0))
    encoded = int(stats.get(encoded_key, 0))
    reconstructed = int(stats.get(reconstructed_key, stats.get("input_bytes", 0)))
    return {
        "payload": payload,
        "payload_note": payload_note,
        "round": round_id,
        "method": method,
        "input_bytes": int(stats.get("input_bytes", reconstructed)),
        "encoded_stream_payload_bytes": encoded,
        "reconstructed_bytes": reconstructed,
        "completion_ms_measured": round(elapsed, 3),
        "reconstructed_rate_mbps_measured": round(reconstructed * 8 / (elapsed / 1000.0) / 1e6, 6)
        if elapsed else 0.0,
        "encoded_rate_mbps_measured": round(encoded * 8 / (elapsed / 1000.0) / 1e6, 6)
        if elapsed else 0.0,
        "reconstruction_ok": bool(stats.get("reconstruction_ok", False)),
        "semantic_misses": int(stats.get("semantic_misses", 0)),
        "repair_full_frames": int(stats.get("repair_full_frames", 0)),
        "emulation": "Linux tc/netem qdisc on loopback; local kernel path emulation, not WAN",
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, float, float, float], dict[int, dict[str, dict[str, Any]]]] = {}
    for row in rows:
        key = (row["payload"], row["rate_mbps"], row["rtt_ms"], row["loss_percent"])
        grouped.setdefault(key, {}).setdefault(int(row["round"]), {})[row["method"]] = row

    summaries = []
    for (payload, rate, rtt, loss), by_round in sorted(grouped.items()):
        completion_ratios = []
        byte_ratios = []
        rl_multipliers = []
        all_rows = []
        for pair in by_round.values():
            if "raw-quic-stream" not in pair or "redulink-binary-quic-stream" not in pair:
                continue
            raw = pair["raw-quic-stream"]
            rl = pair["redulink-binary-quic-stream"]
            all_rows.extend([raw, rl])
            completion_ratios.append(float(rl["completion_ms_measured"]) / float(raw["completion_ms_measured"]))
            byte_ratios.append(float(rl["encoded_stream_payload_bytes"]) / float(raw["encoded_stream_payload_bytes"]))
            rl_multipliers.append(float(rl["reconstructed_bytes"]) / float(rl["encoded_stream_payload_bytes"]))
        if not completion_ratios:
            continue
        comp_lo, comp_hi = bootstrap_ci(completion_ratios)
        byte_lo, byte_hi = bootstrap_ci(byte_ratios)
        mult_lo, mult_hi = bootstrap_ci(rl_multipliers)
        summaries.append({
            "payload": payload,
            "rate_mbps": rate,
            "rtt_ms": rtt,
            "loss_percent": loss,
            "rounds": len(completion_ratios),
            "completion_ratio_mean": round_float(mean(completion_ratios)),
            "completion_ratio_sd": round_float(stdev(completion_ratios)),
            "completion_ratio_ci95_low": round_float(comp_lo),
            "completion_ratio_ci95_high": round_float(comp_hi),
            "encoded_byte_ratio_mean": round_float(mean(byte_ratios)),
            "encoded_byte_ratio_ci95_low": round_float(byte_lo),
            "encoded_byte_ratio_ci95_high": round_float(byte_hi),
            "redulink_stream_multiplier_mean": round_float(mean(rl_multipliers)),
            "redulink_stream_multiplier_ci95_low": round_float(mult_lo),
            "redulink_stream_multiplier_ci95_high": round_float(mult_hi),
            "all_reconstructed": all(r["reconstruction_ok"] for r in all_rows),
        })
    return summaries


async def run_scenario(*, payload: str, rate_mbps: float, rtt_ms: float,
                       loss_percent: float, rounds: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(1, rounds + 1):
        for row in await run_round(payload=payload, round_id=i):
            row["rate_mbps"] = rate_mbps
            row["rtt_ms"] = rtt_ms
            row["loss_percent"] = loss_percent
            rows.append(row)
    return rows


def scenario_grid(args: argparse.Namespace) -> list[dict[str, Any]]:
    return [
        {"payload": payload, "rate_mbps": rate, "rtt_ms": rtt, "loss_percent": loss}
        for payload in args.payload
        for rate in args.rate_mbps
        for rtt in args.rtt_ms
        for loss in args.loss_percent
    ]


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    all_rows: list[dict[str, Any]] = []
    for scenario in scenario_grid(args):
        with netem_context(
            device=args.device,
            rate_mbps=scenario["rate_mbps"],
            rtt_ms=scenario["rtt_ms"],
            loss_percent=scenario["loss_percent"],
            limit_packets=args.limit_packets,
            use_sudo=not args.no_sudo,
        ):
            all_rows.extend(await run_scenario(rounds=args.rounds, **scenario))
    return {
        "experiment": "linux_netem_quic_path",
        "note": "Linux tc/netem qdisc on loopback UDP; local kernel path emulation, not WAN or Mininet.",
        "device": args.device,
        "rows": all_rows,
        "summary": summarize(all_rows),
    }


def write_outputs(result: dict[str, Any], *, output_json: Path, output_csv: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    rows = result["rows"]
    if rows:
        with output_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--payload", choices=["demo", "redis"], nargs="+", default=["demo", "redis"])
    ap.add_argument("--rate-mbps", type=float, nargs="+", default=[5.0, 20.0])
    ap.add_argument("--rtt-ms", type=float, nargs="+", default=[20.0, 80.0])
    ap.add_argument("--loss-percent", type=float, nargs="+", default=[0.0])
    ap.add_argument("--rounds", type=int, default=20)
    ap.add_argument("--device", default="lo")
    ap.add_argument("--limit-packets", type=int, default=10000)
    ap.add_argument("--no-sudo", action="store_true", help="run tc directly, for root shells/CI containers")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--output-json", type=Path, default=ROOT / "results" / "linux_netem_quic_path.json")
    ap.add_argument("--output-csv", type=Path, default=ROOT / "results" / "linux_netem_quic_path.csv")
    args = ap.parse_args()

    scenarios = scenario_grid(args)
    if args.dry_run:
        dry_run = {
            "experiment": "linux_netem_quic_path_dry_run",
            "platform": platform.system(),
            "device": args.device,
            "scenarios": scenarios,
            "setup": [
                setup_commands(
                    device=args.device,
                    rate_mbps=s["rate_mbps"],
                    rtt_ms=s["rtt_ms"],
                    loss_percent=s["loss_percent"],
                    limit_packets=args.limit_packets,
                    use_sudo=not args.no_sudo,
                )[0]
                for s in scenarios
            ],
            "cleanup": cleanup_commands(device=args.device, use_sudo=not args.no_sudo),
        }
        print(json.dumps(dry_run, indent=2, sort_keys=True))
        return

    if platform.system() != "Linux":
        raise SystemExit("Live tc/netem execution requires Linux; use --dry-run on other platforms.")

    result = asyncio.run(main_async(args))
    write_outputs(result, output_json=args.output_json, output_csv=args.output_csv)
    print(json.dumps({
        "experiment": result["experiment"],
        "device": result["device"],
        "summary_rows": len(result["summary"]),
        "output_csv": str(args.output_csv),
        "output_json": str(args.output_json),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
