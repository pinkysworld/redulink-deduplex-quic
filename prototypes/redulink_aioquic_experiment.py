#!/usr/bin/env python3
"""Native QUIC ReduLink stream-mapping experiment using aioquic.

This prototype runs a real QUIC client and server over localhost using the
``aioquic`` library. ReduLink FULL/REF/MISS/repair messages are carried over a
QUIC bidirectional stream as a pre-encryption application mapping. This is not a
custom QUIC extension-frame parser, but it exercises native QUIC handshake,
TLS-protected streams, stream flow control, ACK/loss machinery inside aioquic,
and encrypted UDP packetization.

The experiment deliberately keeps the ReduLink layer small: the client sends a
warm-state update encoded as authenticated FULL/REF frames, the server starts
with a thinned receiver dictionary, the server reports semantic REF misses over
the same QUIC stream, and the client repairs them with authenticated FULL frames.
The final output must match the original update byte-for-byte.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import ssl
import sys
import tempfile
import time
from collections import OrderedDict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

try:
    from aioquic.asyncio import connect, serve
    from aioquic.quic.configuration import QuicConfiguration
except Exception as exc:  # pragma: no cover - tested by import guard in main
    raise SystemExit(
        "aioquic is required for the native QUIC experiment. "
        "Install requirements-dev.txt or run: python3 -m pip install aioquic"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_model as redulink  # noqa: E402
import redulink_secure as secure  # noqa: E402
import redulink_wire as wire  # noqa: E402
import redulink_key_schedule as key_schedule  # noqa: E402

ALPN = ["redulink/1"]
LEN_BYTES = 4
WIRE_FORMAT = "binary"


def _json_bytes(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


async def send_msg(writer: asyncio.StreamWriter, obj: dict[str, Any]) -> int:
    if WIRE_FORMAT == "binary":
        return await wire.send_message(writer, obj)
    payload = _json_bytes(obj)
    writer.write(len(payload).to_bytes(LEN_BYTES, "big") + payload)
    await writer.drain()
    return LEN_BYTES + len(payload)


async def read_msg(reader: asyncio.StreamReader) -> tuple[dict[str, Any], int]:
    if WIRE_FORMAT == "binary":
        return await wire.read_message(reader)
    header = await reader.readexactly(LEN_BYTES)
    length = int.from_bytes(header, "big")
    payload = await reader.readexactly(length)
    return json.loads(payload.decode("utf-8")), LEN_BYTES + length


def frame_to_msg(seq: int, frame: secure.SecureFrame, *, repair: bool = False) -> dict[str, Any]:
    if WIRE_FORMAT == "binary":
        return {"t": "FRAME", "seq": seq, "repair": bool(repair), "frame": frame}
    msg = asdict(frame)
    msg["t"] = "FRAME"
    msg["seq"] = seq
    msg["repair"] = bool(repair)
    msg["payload_b64"] = base64.b64encode(frame.payload).decode("ascii")
    del msg["payload"]
    return msg


def msg_to_frame(msg: dict[str, Any]) -> secure.SecureFrame:
    if "frame" in msg:
        return msg["frame"]
    return secure.SecureFrame(
        kind=str(msg["kind"]),
        epoch=int(msg["epoch"]),
        scope=str(msg["scope"]),
        stream_id=int(msg["stream_id"]),
        offset=int(msg["offset"]),
        cid=str(msg["cid"]),
        length=int(msg["length"]),
        nonce=int(msg["nonce"]),
        tag=str(msg["tag"]),
        payload=base64.b64decode(str(msg.get("payload_b64", "")).encode("ascii")),
    )


def build_secure_dictionary(data: bytes, *, secret: bytes, epoch: int, scope: str,
                            chunker: str, chunk_size: int) -> OrderedDict[str, bytes]:
    d: OrderedDict[str, bytes] = OrderedDict()
    for chunk in redulink.make_chunks(data, chunker, chunk_size):
        redulink.touch_lru(
            d,
            secure.secure_cid(chunk, secret=secret, epoch=epoch, scope=scope),
            chunk,
            redulink.MAX_DICT_CHUNKS,
        )
    return d


def thin_dictionary(dictionary: OrderedDict[str, bytes], *, missing_every: int) -> OrderedDict[str, bytes]:
    kept: OrderedDict[str, bytes] = OrderedDict()
    for idx, (key, value) in enumerate(dictionary.items()):
        if missing_every <= 0 or (idx + 1) % missing_every != 0:
            kept[key] = value
    if dictionary and len(kept) == len(dictionary):
        first = next(iter(kept))
        del kept[first]
    return kept


def make_full_repair(original_ref: secure.SecureFrame, payload: bytes, *, secret: bytes, nonce: int) -> secure.SecureFrame:
    tag = secure.frame_tag(
        secret=secret,
        kind="FULL",
        epoch=original_ref.epoch,
        scope=original_ref.scope,
        stream_id=original_ref.stream_id,
        offset=original_ref.offset,
        cid=original_ref.cid,
        length=len(payload),
        nonce=nonce,
        payload=payload,
    )
    return secure.SecureFrame(
        kind="FULL",
        epoch=original_ref.epoch,
        scope=original_ref.scope,
        stream_id=original_ref.stream_id,
        offset=original_ref.offset,
        cid=original_ref.cid,
        length=len(payload),
        nonce=nonce,
        tag=tag,
        payload=payload,
    )


def demo_payload(blocks: int = 96) -> tuple[bytes, bytes]:
    if blocks < 16:
        raise ValueError("blocks must be at least 16")
    base = []
    for i in range(blocks):
        label = f"quic-block-{i:03d}:".encode("ascii")
        base.append(label + bytes([65 + (i % 26)]) * (1024 - len(label)))
    warm = b"".join(base)
    update = list(base)
    change_positions = sorted({5, 17, 33, max(8, blocks // 3), max(9, (2 * blocks) // 3), blocks - 15})
    letters = [b"x", b"y", b"z", b"q", b"r", b"s"]
    for j, i in enumerate(change_positions):
        if 0 <= i < len(update):
            b = letters[j % len(letters)]
            label = f"quic-changed-{i:05d}:".encode("ascii")
            update[i] = label + b * (1024 - len(label))
    return warm, b"".join(update)


def write_self_signed_cert(directory: Path) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "DE"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ReduLink artifact"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=7))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path = directory / "cert.pem"
    key_path = directory / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


class QuicReduLinkServer:
    def __init__(self, *, warm: bytes, expected_sha256: str, secret: bytes, epoch: int, scope: str,
                 stream_id: int, chunker: str, chunk_size: int, missing_every: int):
        full = build_secure_dictionary(warm, secret=secret, epoch=epoch, scope=scope, chunker=chunker, chunk_size=chunk_size)
        self.dictionary = thin_dictionary(full, missing_every=missing_every)
        self.initial_dictionary_entries = len(self.dictionary)
        self.expected_sha256 = expected_sha256
        self.secret = secret
        self.epoch = epoch
        self.scope = scope
        self.stream_id = stream_id
        self.delivered: dict[int, bytes] = {}
        self.seen_nonces: set[int] = set()
        self.stats: dict[str, Any] = {}

    async def handle_stream(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        client_to_server_bytes = 0
        server_to_client_bytes = 0
        auth_failures = 0
        replay_rejections = 0
        semantic_misses = 0
        repair_full_frames = 0
        full_frames = 0
        ref_frames = 0
        missing: list[dict[str, Any]] = []
        start = time.perf_counter()
        try:
            msg, size = await read_msg(reader)
            client_to_server_bytes += size
            if msg.get("t") != "HELLO":
                server_to_client_bytes += await send_msg(writer, {"t": "ERROR", "error": "missing HELLO"})
                return
            while True:
                msg, size = await read_msg(reader)
                client_to_server_bytes += size
                t = msg.get("t")
                if t == "END_ROUND":
                    server_to_client_bytes += await send_msg(writer, {"t": "MISSING", "items": missing})
                    missing = []
                elif t == "FINISH":
                    output = b"".join(self.delivered[i] for i in sorted(self.delivered))
                    reconstruction_ok = hashlib.sha256(output).hexdigest() == self.expected_sha256
                    stats = {
                        "experiment": "aioquic_native_stream_mapping",
                        "transport": "aioquic QUIC bidirectional stream over localhost UDP",
                        "custom_extension_frames": False,
                        "redulink_mapping": ("compact binary FULL/REF/MISS/repair messages carried inside a QUIC stream" if WIRE_FORMAT == "binary" else "length-prefixed JSON FULL/REF/MISS/repair messages carried inside a QUIC stream"),
                        "reconstruction_ok": reconstruction_ok,
                        "server_reconstructed_bytes": len(output),
                        "client_to_server_stream_payload_bytes": client_to_server_bytes,
                        "server_to_client_stream_payload_bytes": server_to_client_bytes,
                        "server_initial_dictionary_entries": self.initial_dictionary_entries,
                        "server_final_dictionary_entries": len(self.dictionary),
                        "full_frames_accepted": full_frames,
                        "ref_frames_accepted": ref_frames,
                        "semantic_misses": semantic_misses,
                        "repair_full_frames": repair_full_frames,
                        "auth_failures": auth_failures,
                        "replay_rejections": replay_rejections,
                        "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3),
                    }
                    self.stats = stats
                    server_to_client_bytes += await send_msg(writer, {"t": "STATS", "stats": stats})
                    try:
                        writer.write_eof()
                        await writer.drain()
                    except Exception:
                        pass
                    return
                elif t == "FRAME":
                    seq = int(msg["seq"])
                    frame = msg_to_frame(msg)
                    try:
                        secure.verify_frame(
                            frame,
                            secret=self.secret,
                            expected_epoch=self.epoch,
                            expected_scope=self.scope,
                            expected_stream_id=self.stream_id,
                            expected_offset=frame.offset,
                            seen_nonces=self.seen_nonces,
                        )
                    except ValueError as exc:
                        if "replayed" in str(exc):
                            replay_rejections += 1
                        else:
                            auth_failures += 1
                        missing.append({"seq": seq, "error": str(exc)})
                        continue
                    self.seen_nonces.add(frame.nonce)
                    if frame.kind == "FULL":
                        if len(frame.payload) != frame.length:
                            auth_failures += 1
                            missing.append({"seq": seq, "error": "FULL length mismatch"})
                            continue
                        if secure.secure_cid(frame.payload, secret=self.secret, epoch=self.epoch, scope=self.scope) != frame.cid:
                            auth_failures += 1
                            missing.append({"seq": seq, "error": "FULL cid mismatch"})
                            continue
                        redulink.touch_lru(self.dictionary, frame.cid, frame.payload, redulink.MAX_DICT_CHUNKS)
                        self.delivered[seq] = frame.payload
                        full_frames += 1
                        if bool(msg.get("repair", False)):
                            repair_full_frames += 1
                    elif frame.kind == "REF":
                        chunk = self.dictionary.get(frame.cid)
                        if chunk is None or len(chunk) != frame.length:
                            semantic_misses += 1
                            missing.append({"seq": seq, "cid": frame.cid, "length": frame.length})
                        else:
                            self.delivered[seq] = chunk
                            ref_frames += 1
                    else:
                        auth_failures += 1
                        missing.append({"seq": seq, "error": "unknown frame kind"})
                else:
                    server_to_client_bytes += await send_msg(writer, {"t": "ERROR", "error": f"unknown message {t}"})
                    return
        except asyncio.IncompleteReadError:
            return


class LossyUdpProxy(asyncio.DatagramProtocol):
    """Local UDP proxy that drops deterministic datagrams between QUIC endpoints."""
    def __init__(self, server_addr: tuple[str, int], *, loss_every: int = 0):
        self.server_addr = server_addr
        self.loss_every = loss_every
        self.transport: Any = None
        self.client_addr: tuple[str, int] | None = None
        self.c2s_seen = 0
        self.s2c_seen = 0
        self.c2s_dropped = 0
        self.s2c_dropped = 0
        self.c2s_payload_bytes_seen = 0
        self.s2c_payload_bytes_seen = 0
        self.c2s_payload_bytes_forwarded = 0
        self.s2c_payload_bytes_forwarded = 0

    def connection_made(self, transport: Any) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if addr == self.server_addr:
            self.s2c_seen += 1
            self.s2c_payload_bytes_seen += len(data)
            if self.loss_every and self.s2c_seen % self.loss_every == 0:
                self.s2c_dropped += 1
                return
            if self.client_addr is not None:
                self.s2c_payload_bytes_forwarded += len(data)
                self.transport.sendto(data, self.client_addr)
        else:
            self.client_addr = addr
            self.c2s_seen += 1
            self.c2s_payload_bytes_seen += len(data)
            if self.loss_every and self.c2s_seen % self.loss_every == 0:
                self.c2s_dropped += 1
                return
            self.c2s_payload_bytes_forwarded += len(data)
            self.transport.sendto(data, self.server_addr)

    def stats(self) -> dict[str, int]:
        return {
            "proxy_client_to_server_datagrams_seen": self.c2s_seen,
            "proxy_server_to_client_datagrams_seen": self.s2c_seen,
            "proxy_client_to_server_datagrams_dropped": self.c2s_dropped,
            "proxy_server_to_client_datagrams_dropped": self.s2c_dropped,
            "proxy_client_to_server_udp_payload_bytes_seen": self.c2s_payload_bytes_seen,
            "proxy_server_to_client_udp_payload_bytes_seen": self.s2c_payload_bytes_seen,
            "proxy_client_to_server_udp_payload_bytes_forwarded": self.c2s_payload_bytes_forwarded,
            "proxy_server_to_client_udp_payload_bytes_forwarded": self.s2c_payload_bytes_forwarded,
        }


async def run_async(*, warm: bytes, data: bytes, chunk_size: int, missing_every: int,
                    wire_format: str = "binary", loss_every: int = 0,
                    account_datagrams: bool = False) -> dict[str, Any]:
    global WIRE_FORMAT
    WIRE_FORMAT = wire_format
    master_secret = b"redulink-aioquic-artifact-master-secret"
    epoch = 7
    scope = "artifact-aioquic"
    stream_id = 0
    secret = key_schedule.derive_redulink_secret(
        master_secret,
        key_schedule.ReduLinkKeyContext(
            alpn=ALPN[0],
            epoch=epoch,
            scope=scope,
            connection_context=b"localhost-aioquic-stream-mapping",
            stream_context=b"bidirectional-stream-0",
        ),
    )
    frames, initial = secure.encode(
        data,
        warm_dictionary=warm,
        secret=secret,
        epoch=epoch,
        scope=scope,
        stream_id=stream_id,
        chunker="fixed",
        chunk_size=chunk_size,
    )
    sender_dict = build_secure_dictionary(warm, secret=secret, epoch=epoch, scope=scope, chunker="fixed", chunk_size=chunk_size)

    with tempfile.TemporaryDirectory(prefix="redulink-aioquic-") as tmp:
        cert_path, key_path = write_self_signed_cert(Path(tmp))
        server_conf = QuicConfiguration(is_client=False, alpn_protocols=ALPN)
        server_conf.load_cert_chain(str(cert_path), str(key_path))
        client_conf = QuicConfiguration(is_client=True, alpn_protocols=ALPN)
        client_conf.verify_mode = ssl.CERT_NONE

        server_state = QuicReduLinkServer(
            warm=warm,
            expected_sha256=hashlib.sha256(data).hexdigest(),
            secret=secret,
            epoch=epoch,
            scope=scope,
            stream_id=stream_id,
            chunker="fixed",
            chunk_size=chunk_size,
            missing_every=missing_every,
        )

        def stream_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            asyncio.create_task(server_state.handle_stream(reader, writer))

        server = await serve("127.0.0.1", 0, configuration=server_conf, stream_handler=stream_handler)
        assert server._transport is not None  # aioquic server exposes the bound datagram transport
        server_port = int(server._transport.get_extra_info("sockname")[1])
        proxy_transport = None
        proxy_protocol = None
        if loss_every > 0 or account_datagrams:
            loop = asyncio.get_running_loop()
            proxy_protocol = LossyUdpProxy(("127.0.0.1", server_port), loss_every=loss_every)
            proxy_transport, _ = await loop.create_datagram_endpoint(lambda: proxy_protocol, local_addr=("127.0.0.1", 0))
            port = int(proxy_transport.get_extra_info("sockname")[1])
        else:
            port = server_port
        client_to_server_bytes = 0
        server_to_client_bytes = 0
        repaired = 0
        started = time.perf_counter()
        try:
            async with connect("127.0.0.1", port, configuration=client_conf, wait_connected=True) as protocol:
                reader, writer = await protocol.create_stream()
                client_to_server_bytes += await send_msg(writer, {
                    "t": "HELLO",
                    "version": 1,
                    "input_sha256": hashlib.sha256(data).hexdigest(),
                    "chunk_size": chunk_size,
                    "frame_count": len(frames),
                })
                for seq, frame in enumerate(frames):
                    client_to_server_bytes += await send_msg(writer, frame_to_msg(seq, frame))
                client_to_server_bytes += await send_msg(writer, {"t": "END_ROUND"})
                reply, size = await read_msg(reader)
                server_to_client_bytes += size
                assert reply.get("t") == "MISSING", reply
                missing_items = list(reply.get("items", []))
                next_nonce = max(frame.nonce for frame in frames) + 1
                for item in missing_items:
                    if "error" in item:
                        continue
                    seq = int(item["seq"])
                    ref = frames[seq]
                    payload = sender_dict.get(ref.cid)
                    if payload is None:
                        raise RuntimeError(f"sender has no repair payload for seq={seq}")
                    repair = make_full_repair(ref, payload, secret=secret, nonce=next_nonce)
                    next_nonce += 1
                    repaired += 1
                    client_to_server_bytes += await send_msg(writer, frame_to_msg(seq, repair, repair=True))
                client_to_server_bytes += await send_msg(writer, {"t": "FINISH"})
                reply, size = await read_msg(reader)
                server_to_client_bytes += size
                assert reply.get("t") == "STATS", reply
                stats = dict(reply["stats"])
                try:
                    writer.write_eof()
                    await writer.drain()
                except Exception:
                    pass
                writer.close()
                await protocol.ping()
                protocol.close()
        finally:
            if proxy_transport is not None:
                proxy_transport.close()
            server.close()

    elapsed = round((time.perf_counter() - started) * 1000.0, 3)
    stream_total = client_to_server_bytes + server_to_client_bytes
    stats.update({
        "input_bytes": len(data),
        "initial_redulink_model_wire_bytes": initial.wire_bytes,
        "initial_redulink_model_multiplier": round(initial.effective_multiplier, 6),
        "client_full_frames_initial": initial.full_frames,
        "client_ref_frames_initial": initial.ref_frames,
        "client_repair_full_frames_sent": repaired,
        "client_to_server_stream_payload_bytes_observed": client_to_server_bytes,
        "server_to_client_stream_payload_bytes_observed": server_to_client_bytes,
        "quic_stream_payload_total_bytes": stream_total,
        "quic_stream_payload_multiplier_after_repair": round(len(data) / stream_total, 6) if stream_total else 0,
        "client_elapsed_ms": elapsed,
        "aioquic_version": __import__("aioquic").__version__,
        "wire_format": WIRE_FORMAT,
        "datagram_loss_proxy_enabled": loss_every > 0,
        "datagram_loss_every": loss_every,
        "redulink_key_derivation": "HKDF exporter-style artifact key schedule; production profile should use QUIC TLS exporter bytes",
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


def run_experiment(*, chunk_size: int = 1024, missing_every: int = 7, wire_format: str = "binary",
                   loss_every: int = 0, payload_blocks: int = 96,
                   account_datagrams: bool = False) -> dict[str, Any]:
    warm, data = demo_payload(payload_blocks)
    return asyncio.run(run_async(
        warm=warm,
        data=data,
        chunk_size=chunk_size,
        missing_every=missing_every,
        wire_format=wire_format,
        loss_every=loss_every,
        account_datagrams=account_datagrams,
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the native aioquic ReduLink stream-mapping experiment.")
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--missing-every", type=int, default=7)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--wire-format", choices=["binary", "json"], default="binary")
    parser.add_argument("--loss-every", type=int, default=0, help="Drop every Nth UDP datagram through a localhost proxy; 0 disables loss.")
    parser.add_argument("--payload-blocks", type=int, default=96, help="Number of 1 KiB warm/update blocks for scaling runs.")
    args = parser.parse_args()
    stats = run_experiment(chunk_size=args.chunk_size, missing_every=args.missing_every, wire_format=args.wire_format, loss_every=args.loss_every, payload_blocks=args.payload_blocks)
    text = json.dumps(stats, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
