#!/usr/bin/env python3
"""Compare raw QUIC stream transfer with ReduLink binary stream mapping.

This is a live localhost aioquic experiment. It is not a complete congestion
fairness experiment, but it gives reviewers a transport-level baseline: the same
update bytes are sent raw over an encrypted QUIC stream and through ReduLink's
binary stream mapping, with optional deterministic UDP datagram loss.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import ssl
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototypes"))

from aioquic.asyncio import connect, serve  # type: ignore
from aioquic.quic.configuration import QuicConfiguration  # type: ignore
from redulink_aioquic_experiment import (  # type: ignore
    ALPN,
    LossyUdpProxy,
    demo_payload,
    run_experiment as run_redulink,
    write_self_signed_cert,
)


def _pack_stats(stats: dict) -> bytes:
    payload = json.dumps(stats, sort_keys=True, separators=(",", ":")).encode()
    return len(payload).to_bytes(4, "big") + payload


async def run_raw_async(data: bytes, *, loss_every: int = 0, chunk_bytes: int = 4096,
                        account_datagrams: bool = False) -> dict:
    expected = hashlib.sha256(data).hexdigest()
    with tempfile.TemporaryDirectory(prefix="redulink-raw-quic-") as tmp:
        cert, key = write_self_signed_cert(Path(tmp))
        server_conf = QuicConfiguration(is_client=False, alpn_protocols=ALPN)
        server_conf.load_cert_chain(str(cert), str(key))
        client_conf = QuicConfiguration(is_client=True, alpn_protocols=ALPN)
        client_conf.verify_mode = ssl.CERT_NONE

        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            start = time.perf_counter()
            received = await reader.read()
            stats = {
                "transport": "aioquic QUIC bidirectional stream over localhost UDP",
                "method": "raw-quic-stream",
                "input_bytes": len(data),
                "server_received_bytes": len(received),
                "reconstruction_ok": hashlib.sha256(received).hexdigest() == expected,
                "server_elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
            }
            writer.write(_pack_stats(stats))
            await writer.drain()
            try:
                writer.write_eof(); await writer.drain()
            except Exception:
                pass

        def stream_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            asyncio.create_task(handler(reader, writer))

        server = await serve("127.0.0.1", 0, configuration=server_conf, stream_handler=stream_handler)
        assert server._transport is not None
        server_port = int(server._transport.get_extra_info("sockname")[1])
        proxy_transport = None
        proxy_protocol = None
        port = server_port
        if loss_every > 0 or account_datagrams:
            loop = asyncio.get_running_loop()
            proxy_protocol = LossyUdpProxy(("127.0.0.1", server_port), loss_every=loss_every)
            proxy_transport, _ = await loop.create_datagram_endpoint(lambda: proxy_protocol, local_addr=("127.0.0.1", 0))
            port = int(proxy_transport.get_extra_info("sockname")[1])
        start = time.perf_counter()
        stream_payload_bytes = 0
        try:
            async with connect("127.0.0.1", port, configuration=client_conf, wait_connected=True) as protocol:
                reader, writer = await protocol.create_stream()
                for pos in range(0, len(data), chunk_bytes):
                    part = data[pos:pos + chunk_bytes]
                    writer.write(part)
                    stream_payload_bytes += len(part)
                    await writer.drain()
                writer.write_eof(); await writer.drain()
                header = await reader.readexactly(4)
                size = int.from_bytes(header, "big")
                payload = await reader.readexactly(size)
                stats = json.loads(payload.decode())
                protocol.close()
        finally:
            if proxy_transport is not None:
                proxy_transport.close()
            server.close()
        stats.update({
            "client_elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
            "quic_stream_payload_total_bytes": stream_payload_bytes,
            "effective_stream_payload_multiplier": round(len(data) / stream_payload_bytes, 6) if stream_payload_bytes else 0,
            "datagram_loss_proxy_enabled": loss_every > 0,
            "datagram_loss_every": loss_every,
        })
        if proxy_protocol is not None:
            stats.update(proxy_protocol.stats())
            c2s = stats["proxy_client_to_server_udp_payload_bytes_seen"]
            s2c = stats["proxy_server_to_client_udp_payload_bytes_seen"]
            datagrams = stats["proxy_client_to_server_datagrams_seen"] + stats["proxy_server_to_client_datagrams_seen"]
            stats.update({
                "udp_payload_bytes_seen_total": c2s + s2c,
                "udp_payload_multiplier_seen": round(len(data) / (c2s + s2c), 6) if (c2s + s2c) else 0,
                "approx_ipv4_udp_bytes_seen_total": c2s + s2c + 28 * datagrams,
                "approx_ipv4_udp_multiplier_seen": round(len(data) / (c2s + s2c + 28 * datagrams), 6) if datagrams else 0,
                "packet_accounting_note": "UDP payload bytes observed by local proxy; IPv4/UDP total adds 28 bytes per datagram and excludes link-layer overhead.",
            })
        return stats


def run_raw(data: bytes, *, loss_every: int = 0, account_datagrams: bool = False) -> dict:
    return asyncio.run(run_raw_async(data, loss_every=loss_every, account_datagrams=account_datagrams))


def row(method: str, loss: int, stats: dict) -> dict[str, str]:
    return {
        "method": method,
        "loss_every": str(loss),
        "input_bytes": str(stats.get("input_bytes", 0)),
        "stream_payload_bytes": str(stats.get("quic_stream_payload_total_bytes", stats.get("client_to_server_stream_payload_bytes_observed", 0))),
        "udp_payload_bytes_seen": str(stats.get("udp_payload_bytes_seen_total", "")),
        "udp_payload_multiplier_seen": str(stats.get("udp_payload_multiplier_seen", "")),
        "approx_ipv4_udp_bytes_seen": str(stats.get("approx_ipv4_udp_bytes_seen_total", "")),
        "approx_ipv4_udp_multiplier_seen": str(stats.get("approx_ipv4_udp_multiplier_seen", "")),
        "effective_multiplier": str(stats.get("effective_stream_payload_multiplier", stats.get("quic_stream_payload_multiplier_after_repair", 0))),
        "reconstruction_ok": str(stats.get("reconstruction_ok", False)),
        "semantic_misses": str(stats.get("semantic_misses", 0)),
        "repair_full_frames": str(stats.get("repair_full_frames", 0)),
        "client_elapsed_ms": str(stats.get("client_elapsed_ms", "")),
        "proxy_dropped": str(stats.get("proxy_client_to_server_datagrams_dropped", 0) + stats.get("proxy_server_to_client_datagrams_dropped", 0)),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-csv", type=Path, default=ROOT / "results" / "quic_flow_comparison.csv")
    p.add_argument("--output-json", type=Path, default=ROOT / "results" / "quic_flow_comparison.json")
    p.add_argument("--loss-every", type=int, action="append", default=None)
    p.add_argument("--payload-blocks", type=int, default=96)
    args = p.parse_args()
    warm, data = demo_payload(args.payload_blocks)
    results = []
    losses = args.loss_every if args.loss_every is not None else [0, 9]
    for loss in losses:
        raw = run_raw(data, loss_every=loss, account_datagrams=True)
        results.append({"method": "raw-quic-stream", "loss_every": loss, "stats": raw})
        rl = run_redulink(
            chunk_size=1024,
            missing_every=7,
            wire_format="binary",
            loss_every=loss,
            payload_blocks=args.payload_blocks,
            account_datagrams=True,
        )
        results.append({"method": "redulink-binary-quic-stream", "loss_every": loss, "stats": rl})
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps({"results": results}, indent=2, sort_keys=True) + "\n")
    with args.output_csv.open("w", newline="") as fh:
        rows = [row(item["method"], item["loss_every"], item["stats"]) for item in results]
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    print(args.output_csv)


if __name__ == "__main__":
    main()
