#!/usr/bin/env python3
"""Compare raw QUIC stream transfer with ReduLink binary stream mapping.

This live localhost aioquic experiment sends the same update bytes as raw QUIC
application-stream data and through ReduLink's binary stream mapping. The
committed result reports exact reconstruction and application-stream bytes. It
does not report timing, packet-layer bytes, or congestion fairness.
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
                        account_datagrams: bool = False, shaper=None,
                        server_port: int = 0) -> dict:
    end_to_end_started = time.perf_counter()
    expected = hashlib.sha256(data).hexdigest()
    with tempfile.TemporaryDirectory(prefix="redulink-raw-quic-") as tmp:
        cert, key = write_self_signed_cert(Path(tmp))
        server_conf = QuicConfiguration(is_client=False, alpn_protocols=ALPN)
        server_conf.load_cert_chain(str(cert), str(key))
        client_conf = QuicConfiguration(is_client=True, alpn_protocols=ALPN)
        client_conf.verify_mode = ssl.CERT_REQUIRED
        client_conf.cafile = str(cert)

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

        server = await serve("127.0.0.1", server_port, configuration=server_conf, stream_handler=stream_handler)
        assert server._transport is not None
        server_port = int(server._transport.get_extra_info("sockname")[1])
        proxy_transport = None
        proxy_protocol = None
        port = server_port
        if loss_every > 0 or account_datagrams or shaper is not None:
            loop = asyncio.get_running_loop()
            proxy_protocol = LossyUdpProxy(("127.0.0.1", server_port), loss_every=loss_every, shaper=shaper)
            proxy_transport, _ = await loop.create_datagram_endpoint(lambda: proxy_protocol, local_addr=("127.0.0.1", 0))
            port = int(proxy_transport.get_extra_info("sockname")[1])
        network_started = time.perf_counter()
        application_completed = network_started
        stream_payload_bytes = 0
        diagnostic_stats_bytes = 0
        try:
            async with connect("127.0.0.1", port, configuration=client_conf, wait_connected=True) as protocol:
                reader, writer = await protocol.create_stream()
                application_stream_id = int(writer.get_extra_info("stream_id"))
                for pos in range(0, len(data), chunk_bytes):
                    part = data[pos:pos + chunk_bytes]
                    writer.write(part)
                    stream_payload_bytes += len(part)
                    await writer.drain()
                writer.write_eof(); await writer.drain()
                header = await reader.readexactly(4)
                size = int.from_bytes(header, "big")
                payload = await reader.readexactly(size)
                diagnostic_stats_bytes = 4 + size
                stats = json.loads(payload.decode())
                application_completed = time.perf_counter()
                protocol.close()
        finally:
            if proxy_transport is not None:
                proxy_transport.close()
            server.close()
        network_elapsed = round((application_completed - network_started) * 1000, 3)
        end_to_end_elapsed = round((application_completed - end_to_end_started) * 1000, 3)
        setup_elapsed = round((network_started - end_to_end_started) * 1000, 3)
        stats.update({
            "client_elapsed_ms": network_elapsed,
            "client_network_elapsed_ms": network_elapsed,
            "client_end_to_end_elapsed_ms": end_to_end_elapsed,
            "client_preparation_elapsed_ms": 0.0,
            "environment_setup_elapsed_ms": setup_elapsed,
            "client_timing_definition": (
                "connection-and-application timing starts immediately before connect and stops after decoding "
                "the diagnostic stats message; raw transfer requires no representation preparation"
            ),
            "forward_protocol_stream_bytes": stream_payload_bytes,
            "reverse_repair_control_stream_bytes": 0,
            "diagnostic_stats_stream_bytes": diagnostic_stats_bytes,
            "protocol_stream_payload_total_bytes_excluding_diagnostics": stream_payload_bytes,
            "quic_stream_payload_total_bytes": stream_payload_bytes,
            "effective_stream_payload_multiplier": round(len(data) / stream_payload_bytes, 6) if stream_payload_bytes else 0,
            "stream_accounting_definition": (
                "protocol stream bytes contain the raw application body; the diagnostic stats response is "
                "reported separately and excluded from the multiplier"
            ),
            "datagram_loss_proxy_enabled": loss_every > 0,
            "datagram_loss_every": loss_every,
            "tls_server_certificate_verified": True,
            "tls_client_certificate_used": False,
            "application_stream_id": application_stream_id,
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
        "stream_payload_bytes": str(stats.get("protocol_stream_payload_total_bytes_excluding_diagnostics", stats.get("quic_stream_payload_total_bytes", 0))),
        "forward_protocol_stream_bytes": str(stats.get("forward_protocol_stream_bytes", "")),
        "reverse_repair_control_stream_bytes": str(stats.get("reverse_repair_control_stream_bytes", "")),
        "diagnostic_stats_stream_bytes": str(stats.get("diagnostic_stats_stream_bytes", "")),
        "effective_multiplier": str(stats.get("effective_stream_payload_multiplier", stats.get("quic_stream_payload_multiplier_after_repair", 0))),
        "reconstruction_ok": str(stats.get("reconstruction_ok", False)),
        "semantic_misses": str(stats.get("semantic_misses", 0)),
        "repair_full_frames": str(stats.get("repair_full_frames", 0)),
        "application_stream_id": str(stats.get("application_stream_id", "")),
        "tls_server_certificate_verified": str(stats.get("tls_server_certificate_verified", False)),
        "tls_client_certificate_used": str(stats.get("tls_client_certificate_used", False)),
        "tls_exporter_live": str(stats.get("tls_exporter_live", "not_applicable")),
        "tls_exporter_outputs_match": str(stats.get(
            "tls_exporter_outputs_match", "not_applicable",
        )),
        "tls_exporter_bridge": str(stats.get(
            "tls_exporter_bridge", "not applicable to raw QUIC stream",
        )),
        "redulink_key_derivation": str(stats.get(
            "redulink_key_derivation",
            "not applicable to raw QUIC stream; QUIC/TLS provides transport protection",
        )),
        "tls_exporter_invocation": str(stats.get(
            "tls_exporter_invocation", "not applicable to raw QUIC stream",
        )),
        "record_mac_transcript": str(stats.get(
            "record_mac_transcript", "not applicable to raw QUIC stream",
        )),
        "chunk_size_bytes": str(stats.get("chunk_size_bytes", "not_applicable")),
        "receiver_dictionary_thinning_every": str(stats.get(
            "receiver_dictionary_thinning_every", "not_applicable",
        )),
        "sender_dictionary_budget_chunks": str(stats.get(
            "sender_dictionary_budget_chunks", "not_applicable",
        )),
        "receiver_dictionary_budget_chunks": str(stats.get(
            "receiver_dictionary_budget_chunks", "not_applicable",
        )),
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
    losses = args.loss_every if args.loss_every is not None else [0]
    for loss in losses:
        raw = run_raw(data, loss_every=loss, account_datagrams=False)
        results.append({"method": "raw-quic-stream", "loss_every": loss, "stats": raw})
        rl = run_redulink(
            chunk_size=1024,
            missing_every=7,
            wire_format="binary",
            loss_every=loss,
            payload_blocks=args.payload_blocks,
            account_datagrams=False,
        )
        results.append({"method": "redulink-binary-quic-stream", "loss_every": loss, "stats": rl})
    rows = [row(item["method"], item["loss_every"], item["stats"]) for item in results]
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps({
        "experiment": "zero_loss_aioquic_protocol_stream_accounting",
        "accounting_layer": "QUIC application-stream bytes; diagnostic STATS reported separately",
        "results": rows,
    }, indent=2, sort_keys=True) + "\n")
    with args.output_csv.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    print(args.output_csv)


if __name__ == "__main__":
    main()
