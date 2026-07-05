#!/usr/bin/env python3
"""macOS pf/dnctl path-emulation benchmark for native aioquic flows.

This benchmark is the local-Mac replacement for the userspace asyncio shaper.
It runs raw QUIC and ReduLink binary-stream transfers while a temporary pf
anchor applies dummynet pipes to loopback UDP traffic. It requires sudo for the
live run, but ``--dry-run`` prints the exact commands and pf rules without
changing system networking.

The script always attempts cleanup after a live run: it flushes the ReduLink
anchor and deletes the configured dummynet pipes. It does not modify the main
pf.conf file; it loads a temporary anchor below macOS' existing com.apple/*
dummynet anchor point.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "prototypes"))

from stats_utils import bootstrap_ci, mean, round_float, stdev  # type: ignore

ANCHOR = "com.apple/redulink_dummynet"
PIPE_IN = 48101
PIPE_OUT = 48102


def pf_rules(*, pipe_in: int, pipe_out: int, interface: str = "lo0",
             direction: str = "out", ports: list[int] | None = None) -> str:
    rules = []
    port_suffixes = [""]
    if ports:
        port_suffixes = [f" port {int(port)}" for port in ports]
    if direction in {"in", "both"}:
        for suffix in port_suffixes:
            rules.append(
                f"dummynet in quick on {interface} inet proto udp "
                f"from 127.0.0.1{suffix} to 127.0.0.1 pipe {pipe_in}"
            )
    if direction in {"out", "both"}:
        for suffix in port_suffixes:
            rules.append(
                f"dummynet out quick on {interface} inet proto udp "
                f"from 127.0.0.1 to 127.0.0.1{suffix} pipe {pipe_out}"
            )
    return "\n".join(rules) + "\n"


def setup_commands(*, rate_mbps: float, rtt_ms: float, loss_percent: float,
                   pipe_in: int = PIPE_IN, pipe_out: int = PIPE_OUT,
                   interface: str = "lo0", anchor: str = ANCHOR,
                   rules_path: Path | None = None,
                   queue_kbytes: int = 512) -> list[list[str]]:
    delay_ms = max(0.0, rtt_ms / 2.0)
    plr = max(0.0, min(1.0, loss_percent / 100.0))
    rules = str(rules_path or Path("/tmp/redulink_dummynet.pf"))
    pipe_args = [
        "config", "bw", f"{rate_mbps}Mbit/s", "delay", f"{delay_ms}ms",
        "queue", f"{queue_kbytes}Kbytes",
    ]
    if plr:
        pipe_args.extend(["plr", f"{plr:.6f}"])
    return [
        ["sudo", "dnctl", "pipe", str(pipe_in), *pipe_args],
        ["sudo", "dnctl", "pipe", str(pipe_out), *pipe_args],
        ["sudo", "pfctl", "-E"],
        ["sudo", "pfctl", "-a", anchor, "-f", rules],
    ]


def cleanup_commands(*, pipe_in: int = PIPE_IN, pipe_out: int = PIPE_OUT,
                     anchor: str = ANCHOR) -> list[list[str]]:
    return [
        ["sudo", "pfctl", "-a", anchor, "-F", "all"],
        ["sudo", "dnctl", "pipe", str(pipe_in), "delete"],
        ["sudo", "dnctl", "pipe", str(pipe_out), "delete"],
    ]


def run_cmd(cmd: list[str]) -> None:
    if os.geteuid() == 0 and cmd and cmd[0] == "sudo":
        cmd = cmd[1:]
    subprocess.run(cmd, check=True)


def reserve_udp_ports(count: int) -> list[int]:
    sockets = []
    try:
        for _ in range(count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
        return [int(sock.getsockname()[1]) for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


def scenario_ports(args: argparse.Namespace) -> tuple[int, int]:
    if args.raw_server_port or args.redulink_server_port:
        if not (args.raw_server_port and args.redulink_server_port):
            raise SystemExit("--raw-server-port and --redulink-server-port must be provided together")
        if args.raw_server_port == args.redulink_server_port:
            raise SystemExit("raw and ReduLink server ports must differ")
        return int(args.raw_server_port), int(args.redulink_server_port)
    return tuple(reserve_udp_ports(2))  # type: ignore[return-value]


@contextmanager
def dummynet_context(*, rate_mbps: float, rtt_ms: float, loss_percent: float,
                    dry_run: bool, interface: str = "lo0", direction: str = "out",
                    queue_kbytes: int = 512, ports: list[int] | None = None):
    with tempfile.TemporaryDirectory(prefix="redulink-dummynet-") as td:
        rules_path = Path(td) / "anchor.pf"
        rules_text = pf_rules(
            pipe_in=PIPE_IN,
            pipe_out=PIPE_OUT,
            interface=interface,
            direction=direction,
            ports=ports,
        )
        rules_path.write_text(rules_text, encoding="utf-8")
        setup = setup_commands(
            rate_mbps=rate_mbps,
            rtt_ms=rtt_ms,
            loss_percent=loss_percent,
            interface=interface,
            rules_path=rules_path,
            queue_kbytes=queue_kbytes,
        )
        cleanup = cleanup_commands()
        if dry_run:
            yield {"rules": rules_text, "setup": setup, "cleanup": cleanup, "cleanup_ok": True}
            return
        cleanup_ok = False
        try:
            for cmd in setup:
                run_cmd(cmd)
            yield {"rules": rules_text, "setup": setup, "cleanup": cleanup, "cleanup_ok": False}
        finally:
            failures = []
            for cmd in cleanup:
                try:
                    run_cmd(cmd)
                except Exception as exc:  # best-effort cleanup; record failures in caller metadata
                    failures.append({"cmd": cmd, "error": str(exc)})
            cleanup_ok = not failures
            if not cleanup_ok:
                print(f"WARNING: dummynet cleanup failures: {failures}", file=sys.stderr)


def load_payload(payload: str) -> tuple[bytes, bytes, str]:
    from run_quic_emulated_path import _load_payload  # type: ignore

    return _load_payload(payload)


async def run_pair(*, warm: bytes, data: bytes, payload_note: str,
                   raw_server_port: int = 0,
                   redulink_server_port: int = 0) -> dict[str, Any]:
    from run_quic_flow_comparison import run_raw_async  # type: ignore
    from redulink_aioquic_experiment import run_async as run_redulink_async  # type: ignore

    raw = await run_raw_async(
        data,
        loss_every=0,
        account_datagrams=False,
        server_port=raw_server_port,
    )
    await asyncio.sleep(0.2)
    rl = await run_redulink_async(
        warm=warm,
        data=data,
        chunk_size=1024,
        missing_every=7,
        wire_format="binary",
        loss_every=0,
        account_datagrams=False,
        server_port=redulink_server_port,
    )
    return {"payload_note": payload_note, "raw": raw, "redulink": rl}


async def run_pair_with_dummynet(*, scenario: dict[str, Any], warm: bytes, data: bytes,
                                 payload_note: str, raw_server_port: int,
                                 redulink_server_port: int,
                                 interface: str, direction: str,
                                 queue_kbytes: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="redulink-dummynet-") as td:
        rules_path = Path(td) / "anchor.pf"
        rules_text = pf_rules(
            pipe_in=PIPE_IN,
            pipe_out=PIPE_OUT,
            interface=interface,
            direction=direction,
            ports=[raw_server_port, redulink_server_port],
        )
        rules_path.write_text(rules_text, encoding="utf-8")
        setup = setup_commands(
            rate_mbps=float(scenario["rate_mbps"]),
            rtt_ms=float(scenario["rtt_ms"]),
            loss_percent=float(scenario["loss_percent"]),
            rules_path=rules_path,
            queue_kbytes=queue_kbytes,
        )
        cleanup = cleanup_commands()
        try:
            for cmd in setup:
                run_cmd(cmd)
            return await run_pair(
                warm=warm,
                data=data,
                payload_note=payload_note,
                raw_server_port=raw_server_port,
                redulink_server_port=redulink_server_port,
            )
        finally:
            failures = []
            for cmd in cleanup:
                try:
                    run_cmd(cmd)
                except Exception as exc:
                    failures.append({"cmd": cmd, "error": str(exc)})
            if failures:
                print(f"WARNING: dummynet cleanup failures: {failures}", file=sys.stderr)


async def run_pair_with_dummynet_context_probe(*, scenario: dict[str, Any], warm: bytes, data: bytes,
                                               payload_note: str, raw_server_port: int,
                                               redulink_server_port: int,
                                               interface: str, direction: str,
                                               queue_kbytes: int) -> dict[str, Any]:
    with dummynet_context(
        rate_mbps=float(scenario["rate_mbps"]),
        rtt_ms=float(scenario["rtt_ms"]),
        loss_percent=float(scenario["loss_percent"]),
        dry_run=False,
        interface=interface,
        direction=direction,
        queue_kbytes=queue_kbytes,
        ports=[raw_server_port, redulink_server_port],
    ):
        return await run_pair(
            warm=warm,
            data=data,
            payload_note=payload_note,
            raw_server_port=raw_server_port,
            redulink_server_port=redulink_server_port,
        )


def row_from_stats(*, scenario: dict[str, Any], round_id: int, stats: dict[str, Any]) -> dict[str, Any]:
    raw = stats["raw"]
    rl = stats["redulink"]
    raw_ms = float(raw.get("client_elapsed_ms", 0.0))
    rl_ms = float(rl.get("client_elapsed_ms", 0.0))
    raw_enc = int(raw.get("quic_stream_payload_total_bytes", raw.get("server_received_bytes", 0)))
    rl_enc = int(rl.get("quic_stream_payload_total_bytes", 0))
    raw_recon = int(raw.get("server_received_bytes", 0))
    rl_recon = int(rl.get("server_reconstructed_bytes", 0))
    return {
        **scenario,
        "round": round_id,
        "payload_note": stats["payload_note"],
        "raw_completion_ms": round_float(raw_ms, 3),
        "redulink_completion_ms": round_float(rl_ms, 3),
        "rl_over_raw_completion": round_float(rl_ms / raw_ms if raw_ms else 0.0),
        "raw_encoded_stream_bytes": raw_enc,
        "redulink_encoded_stream_bytes": rl_enc,
        "encoded_byte_ratio_rl_over_raw": round_float(rl_enc / raw_enc if raw_enc else 0.0),
        "raw_reconstructed_bytes": raw_recon,
        "redulink_reconstructed_bytes": rl_recon,
        "redulink_stream_multiplier": round_float(rl_recon / rl_enc if rl_enc else 0.0),
        "semantic_misses": int(rl.get("semantic_misses", 0)),
        "repair_full_frames": int(rl.get("repair_full_frames", 0)),
        "all_reconstructed": bool(raw.get("reconstruction_ok")) and bool(rl.get("reconstruction_ok")),
        "platform": platform.platform(),
        "emulation": "macOS pf/dnctl dummynet on loopback UDP; local kernel path emulation, not WAN",
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    keys = ("payload", "rate_mbps", "rtt_ms", "loss_percent")
    for row in rows:
        groups.setdefault(tuple(row[k] for k in keys), []).append(row)
    out = []
    for key, sel in sorted(groups.items()):
        ratios = [float(r["rl_over_raw_completion"]) for r in sel]
        enc = [float(r["encoded_byte_ratio_rl_over_raw"]) for r in sel]
        mult = [float(r["redulink_stream_multiplier"]) for r in sel]
        ci_lo, ci_hi = bootstrap_ci(ratios)
        enc_lo, enc_hi = bootstrap_ci(enc)
        out.append({
            "payload": key[0],
            "rate_mbps": key[1],
            "rtt_ms": key[2],
            "loss_percent": key[3],
            "rounds": len(sel),
            "rl_over_raw_completion_mean": round_float(mean(ratios)),
            "rl_over_raw_completion_sd": round_float(stdev(ratios)),
            "rl_over_raw_completion_ci95_low": round_float(ci_lo),
            "rl_over_raw_completion_ci95_high": round_float(ci_hi),
            "encoded_byte_ratio_mean": round_float(mean(enc)),
            "encoded_byte_ratio_ci95_low": round_float(enc_lo),
            "encoded_byte_ratio_ci95_high": round_float(enc_hi),
            "redulink_stream_multiplier_mean": round_float(mean(mult)),
            "semantic_misses_mean": round_float(mean(float(r["semantic_misses"]) for r in sel), 3),
            "all_reconstructed": all(bool(r["all_reconstructed"]) for r in sel),
        })
    return out


def scenario_grid(args: argparse.Namespace) -> list[dict[str, Any]]:
    return [
        {"payload": payload, "rate_mbps": rate, "rtt_ms": rtt, "loss_percent": loss}
        for payload in args.payload
        for rate in args.rate_mbps
        for rtt in args.rtt_ms
        for loss in args.loss_percent
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--payload", choices=["demo", "redis"], nargs="+", default=["demo", "redis"])
    ap.add_argument("--rate-mbps", type=float, nargs="+", default=[5.0, 20.0, 100.0])
    ap.add_argument("--rtt-ms", type=float, nargs="+", default=[20.0, 80.0])
    ap.add_argument("--loss-percent", type=float, nargs="+", default=[0.0, 0.1, 1.0])
    ap.add_argument("--rounds", type=int, default=25)
    ap.add_argument("--interface", default="lo0")
    ap.add_argument("--direction", choices=["out", "in", "both"], default="out")
    ap.add_argument("--queue-kbytes", type=int, default=512)
    ap.add_argument("--raw-server-port", type=int, default=0)
    ap.add_argument("--redulink-server-port", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--output-json", type=Path, default=ROOT / "results" / "macos_dummynet_quic_path.json")
    ap.add_argument("--output-csv", type=Path, default=ROOT / "results" / "macos_dummynet_quic_path.csv")
    args = ap.parse_args()

    rows: list[dict[str, Any]] = []
    dry_runs = []
    for scenario in scenario_grid(args):
        if args.dry_run:
            warm = data = b""
            payload_note = ""
        else:
            warm, data, payload_note = load_payload(str(scenario["payload"]))
        raw_server_port, redulink_server_port = scenario_ports(args)
        if args.dry_run:
            with dummynet_context(
                rate_mbps=float(scenario["rate_mbps"]),
                rtt_ms=float(scenario["rtt_ms"]),
                loss_percent=float(scenario["loss_percent"]),
                dry_run=True,
                interface=args.interface,
                direction=args.direction,
                queue_kbytes=args.queue_kbytes,
                ports=[raw_server_port, redulink_server_port],
            ) as dn:
                dry_runs.append({
                    **scenario,
                    "raw_server_port": raw_server_port,
                    "redulink_server_port": redulink_server_port,
                    **dn,
                })
            continue
        for round_id in range(1, args.rounds + 1):
            stats = asyncio.run(run_pair_with_dummynet(
                scenario=scenario,
                warm=warm,
                data=data,
                payload_note=payload_note,
                raw_server_port=raw_server_port,
                redulink_server_port=redulink_server_port,
                interface=args.interface,
                direction=args.direction,
                queue_kbytes=args.queue_kbytes,
            ))
            rows.append(row_from_stats(scenario=scenario, round_id=round_id, stats=stats))

    if args.dry_run:
        result = {
            "experiment": "macos_dummynet_quic_path_dry_run",
            "dry_runs": dry_runs,
        }
        print(json.dumps(result, indent=2))
        return

    summary = summarize(rows)
    result = {
        "experiment": "macos_dummynet_quic_path",
        "note": "macOS pf/dnctl dummynet on loopback UDP; local kernel path emulation, not WAN",
        "rows": rows,
        "summary": summary,
    }
    args.output_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with args.output_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary)
    for item in summary:
        print(item)
    print(args.output_csv)


if __name__ == "__main__":
    main()
