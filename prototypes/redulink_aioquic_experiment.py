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
import hmac
import ipaddress
import json
import secrets
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
import redulink_tls_exporter as tls_exporter  # noqa: E402

if tls_exporter.EXPORTER_LABEL != key_schedule.DEFAULT_LABEL:
    raise RuntimeError("TLS exporter and ReduLink key-schedule labels differ")
tls_exporter.install_aioquic_exporter_bridge()

ALPN = ["redulink/1"]
LEN_BYTES = 4
WIRE_FORMAT = "binary"
PROTOCOL_VERSION = 1
SEND_DRAIN_BYTES = 64 * 1024


def _json_bytes(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def encode_msg(obj: dict[str, Any]) -> bytes:
    if WIRE_FORMAT == "binary":
        return wire.encode_message(obj)
    payload = _json_bytes(obj)
    return len(payload).to_bytes(LEN_BYTES, "big") + payload


async def send_msg(writer: asyncio.StreamWriter, obj: dict[str, Any]) -> int:
    data = encode_msg(obj)
    writer.write(data)
    await writer.drain()
    return len(data)


async def send_msgs_batched(
    writer: asyncio.StreamWriter,
    messages: Any,
    *,
    drain_bytes: int = SEND_DRAIN_BYTES,
) -> int:
    """Send length-delimited messages with bounded, transport-neutral batching."""
    if drain_bytes < 1:
        raise ValueError("drain_bytes must be positive")
    total = 0
    pending = 0
    for obj in messages:
        data = encode_msg(obj)
        writer.write(data)
        total += len(data)
        pending += len(data)
        if pending >= drain_bytes:
            await writer.drain()
            pending = 0
    if pending:
        await writer.drain()
    return total


async def read_msg(reader: asyncio.StreamReader) -> tuple[dict[str, Any], int]:
    if WIRE_FORMAT == "binary":
        return await wire.read_message(reader)
    header = await reader.readexactly(LEN_BYTES)
    length = int.from_bytes(header, "big")
    if length < 1 or length > wire.MAX_MESSAGE_BYTES:
        raise ValueError(f"message length must be between 1 and {wire.MAX_MESSAGE_BYTES} bytes")
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
                            chunker: str, chunk_size: int,
                            max_dict_chunks: int | None = None) -> OrderedDict[str, bytes]:
    d: OrderedDict[str, bytes] = OrderedDict()
    for chunk in redulink.make_chunks(data, chunker, chunk_size):
        redulink.touch_lru(
            d,
            secure.secure_cid(chunk, secret=secret, epoch=epoch, scope=scope),
            chunk,
            max_dict_chunks or redulink.MAX_DICT_CHUNKS,
        )
    return d


def thin_dictionary(dictionary: OrderedDict[str, bytes], *, missing_every: int) -> OrderedDict[str, bytes]:
    if missing_every <= 0:
        return OrderedDict(dictionary)
    kept: OrderedDict[str, bytes] = OrderedDict()
    for idx, (key, value) in enumerate(dictionary.items()):
        if (idx + 1) % missing_every != 0:
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


def validate_missing_items(
    items: list[dict[str, Any]], frames: list[secure.SecureFrame],
) -> list[tuple[int, secure.SecureFrame]]:
    """Validate a complete batched repair request before sending any literal."""
    if len(items) > wire.MAX_MISSING_ITEMS:
        raise RuntimeError("repair request exceeds the single-batch item bound")
    seen: set[int] = set()
    validated: list[tuple[int, secure.SecureFrame]] = []
    for item in items:
        seq = int(item["seq"])
        if seq < 0 or seq >= len(frames):
            raise RuntimeError(f"invalid repair sequence: {seq}")
        if seq in seen:
            raise RuntimeError(f"duplicate repair sequence: {seq}")
        ref = frames[seq]
        if ref.kind != "REF":
            raise RuntimeError(f"receiver requested repair for non-REF seq={seq}")
        if str(item["cid"]) != ref.cid:
            raise RuntimeError(f"receiver repair identifier mismatch for seq={seq}")
        if int(item["length"]) != ref.length:
            raise RuntimeError(f"receiver repair length mismatch for seq={seq}")
        seen.add(seq)
        validated.append((seq, ref))
    return validated


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
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            ]),
            critical=False,
        )
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
    def __init__(self, *, warm: bytes, expected_sha256: str, expected_length: int,
                 secret: bytes, epoch: int, scope: str,
                 stream_id: int, chunker: str, chunk_size: int, missing_every: int,
                 max_dict_chunks: int | None = None,
                 max_reconstructed_bytes: int = secure.DEFAULT_MAX_RECONSTRUCTED_BYTES,
                 tls_exporter_output_sha256: str | None = None):
        self.max_dict_chunks = max_dict_chunks or redulink.MAX_DICT_CHUNKS
        full = build_secure_dictionary(warm, secret=secret, epoch=epoch, scope=scope, chunker=chunker, chunk_size=chunk_size, max_dict_chunks=self.max_dict_chunks)
        self.dictionary = thin_dictionary(full, missing_every=missing_every)
        self.initial_dictionary_entries = len(self.dictionary)
        self.expected_sha256 = expected_sha256
        self.expected_input_length = int(expected_length)
        self.max_reconstructed_bytes = int(max_reconstructed_bytes)
        if self.expected_input_length < 0:
            raise ValueError("expected length must be non-negative")
        if self.expected_input_length > self.max_reconstructed_bytes:
            raise ValueError("expected length exceeds reconstructed-byte quota")
        self.secret = secret
        self.epoch = epoch
        self.scope = scope
        self.stream_id = stream_id
        self.chunk_size = chunk_size
        self.delivered: dict[int, bytes] = {}
        self.seen_nonces = secure.NonceWindow()
        self.expected_frame_count: int | None = None
        self.next_initial_seq = 0
        self.next_initial_offset = 0
        self.pending_repairs: dict[int, tuple[str, int, int]] = {}
        self.round_ended = False
        self.stats: dict[str, Any] = {}
        self.tls_exporter_output_sha256 = tls_exporter_output_sha256

    def accept_hello(self, msg: dict[str, Any]) -> None:
        if int(msg.get("version", -1)) != PROTOCOL_VERSION:
            raise ValueError("unsupported protocol version")
        if int(msg.get("chunk_size", -1)) != self.chunk_size:
            raise ValueError("chunk size mismatch")
        if str(msg.get("input_sha256", "")) != self.expected_sha256:
            raise ValueError("input digest mismatch")
        if int(msg.get("input_length", -1)) != self.expected_input_length:
            raise ValueError("input length mismatch")
        frame_count = int(msg.get("frame_count", -1))
        expected_frames = (
            (self.expected_input_length + self.chunk_size - 1) // self.chunk_size
            if self.expected_input_length else 0
        )
        if frame_count != expected_frames:
            raise ValueError("frame count does not match fixed-size reconstruction")
        if frame_count > wire.MAX_MISSING_ITEMS:
            raise ValueError("frame count exceeds single-batch repair bound")
        self.expected_frame_count = frame_count

    def accept_frame(self, *, seq: int, frame: secure.SecureFrame, repair: bool) -> str:
        """Validate authenticated state before mutating reconstruction state."""
        if self.expected_frame_count is None:
            raise ValueError("HELLO not accepted")
        if repair:
            if not self.round_ended:
                raise ValueError("repair before END_ROUND")
            expected = self.pending_repairs.get(seq)
            if expected is None:
                raise ValueError("unexpected repair sequence")
            expected_cid, expected_length, expected_offset = expected
            if frame.kind != "FULL":
                raise ValueError("repair must be FULL")
            if frame.cid != expected_cid or frame.length != expected_length:
                raise ValueError("repair metadata mismatch")
        else:
            if self.round_ended:
                raise ValueError("initial frame after END_ROUND")
            if seq != self.next_initial_seq or seq >= self.expected_frame_count:
                raise ValueError("unexpected initial sequence")
            expected_offset = self.next_initial_offset

        if frame.length <= 0 or frame.length > self.chunk_size:
            raise ValueError("frame expansion exceeds negotiated chunk bound")
        if expected_offset + frame.length > self.expected_input_length:
            raise ValueError("frame exceeds authenticated transfer length")
        if expected_offset + frame.length > self.max_reconstructed_bytes:
            raise ValueError("reconstructed byte limit exceeded")

        secure.verify_frame(
            frame,
            secret=self.secret,
            expected_epoch=self.epoch,
            expected_scope=self.scope,
            expected_stream_id=self.stream_id,
            expected_offset=expected_offset,
            seen_nonces=self.seen_nonces,
        )
        self.seen_nonces.add(frame.nonce)

        if frame.kind == "FULL":
            if len(frame.payload) != frame.length:
                raise ValueError("FULL length mismatch")
            if secure.secure_cid(
                frame.payload, secret=self.secret, epoch=self.epoch, scope=self.scope,
            ) != frame.cid:
                raise ValueError("FULL cid mismatch")
            redulink.touch_lru(self.dictionary, frame.cid, frame.payload, self.max_dict_chunks)
            self.delivered[seq] = frame.payload
            result = "repair" if repair else "full"
            if repair:
                del self.pending_repairs[seq]
        elif frame.kind == "REF":
            if repair:
                raise ValueError("repair must be FULL")
            chunk = self.dictionary.get(frame.cid)
            if chunk is None:
                self.pending_repairs[seq] = (frame.cid, frame.length, frame.offset)
                result = "miss"
            elif len(chunk) != frame.length:
                raise ValueError("REF length mismatch")
            elif secure.secure_cid(
                chunk, secret=self.secret, epoch=self.epoch, scope=self.scope,
            ) != frame.cid:
                raise ValueError("REF dictionary chunk id mismatch")
            else:
                redulink.touch_lru(self.dictionary, frame.cid, chunk, self.max_dict_chunks)
                self.delivered[seq] = chunk
                result = "ref"
        else:
            raise ValueError("unknown frame kind")

        if not repair:
            self.next_initial_seq += 1
            self.next_initial_offset += frame.length
        return result

    def finalize_reconstruction(self) -> bytes:
        """Return the complete output or fail closed on phase, length, or digest."""
        if not self.round_ended or self.pending_repairs:
            raise ValueError("unfinished reconstruction")
        expected_sequences = set(range(self.expected_frame_count or 0))
        if set(self.delivered) != expected_sequences:
            raise ValueError("incomplete reconstruction sequence")
        output = b"".join(self.delivered[i] for i in range(self.expected_frame_count or 0))
        if len(output) != self.expected_input_length:
            raise ValueError("final reconstructed length mismatch")
        if hashlib.sha256(output).hexdigest() != self.expected_sha256:
            raise ValueError("final reconstructed digest mismatch")
        return output

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
        first_reconstructed_byte_at: float | None = None
        first_byte_measurement_sent = False
        try:
            msg, size = await read_msg(reader)
            client_to_server_bytes += size
            if msg.get("t") != "HELLO":
                server_to_client_bytes += await send_msg(writer, {"t": "ERROR", "error": "missing HELLO"})
                return
            try:
                self.accept_hello(msg)
            except (TypeError, ValueError) as exc:
                server_to_client_bytes += await send_msg(writer, {"t": "ERROR", "error": str(exc)})
                return
            while True:
                msg, size = await read_msg(reader)
                client_to_server_bytes += size
                t = msg.get("t")
                if t == "END_ROUND":
                    if self.round_ended or self.next_initial_seq != self.expected_frame_count:
                        server_to_client_bytes += await send_msg(writer, {"t": "ERROR", "error": "incomplete or duplicate initial round"})
                        return
                    self.round_ended = True
                    missing = [
                        {"seq": seq, "cid": cid, "length": length}
                        for seq, (cid, length, _offset) in sorted(self.pending_repairs.items())
                    ]
                    server_to_client_bytes += await send_msg(writer, {"t": "MISSING", "items": missing})
                elif t == "FINISH":
                    try:
                        output = self.finalize_reconstruction()
                    except ValueError as exc:
                        server_to_client_bytes += await send_msg(writer, {"t": "ERROR", "error": str(exc)})
                        return
                    completed_at = time.perf_counter()
                    stats = {
                        "experiment": "aioquic_native_stream_mapping",
                        "transport": "aioquic QUIC bidirectional stream over localhost UDP",
                        "custom_extension_frames": False,
                        "redulink_mapping": ("compact binary FULL/REF/MISS/repair messages carried inside a QUIC stream" if WIRE_FORMAT == "binary" else "length-prefixed JSON FULL/REF/MISS/repair messages carried inside a QUIC stream"),
                        "reconstruction_ok": True,
                        "server_reconstructed_bytes": len(output),
                        "authenticated_transfer_length": self.expected_input_length,
                        "reconstructed_byte_quota": self.max_reconstructed_bytes,
                        "application_stream_id": self.stream_id,
                        "client_to_server_stream_payload_bytes": client_to_server_bytes,
                        "server_to_client_stream_payload_bytes": server_to_client_bytes,
                        "server_initial_dictionary_entries": self.initial_dictionary_entries,
                        "server_final_dictionary_entries": len(self.dictionary),
                        "server_dictionary_budget_chunks": self.max_dict_chunks,
                        "full_frames_accepted": full_frames,
                        "ref_frames_accepted": ref_frames,
                        "semantic_misses": semantic_misses,
                        "repair_full_frames": repair_full_frames,
                        "auth_failures": auth_failures,
                        "replay_rejections": replay_rejections,
                        "elapsed_ms": round((completed_at - start) * 1000.0, 3),
                        "server_completion_ms": round((completed_at - start) * 1000.0, 3),
                        "server_time_to_first_reconstructed_byte_ms": round(
                            ((first_reconstructed_byte_at or completed_at) - start) * 1000.0,
                            3,
                        ),
                        "server_timing_definition": (
                            "single server monotonic clock from stream-handler entry to availability "
                            "of logical byte offset zero and exact completed reconstruction; no "
                            "cross-host clock subtraction"
                        ),
                    }
                    if self.tls_exporter_output_sha256 is not None:
                        stats["tls_exporter_output_sha256"] = self.tls_exporter_output_sha256
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
                        outcome = self.accept_frame(
                            seq=seq, frame=frame, repair=bool(msg.get("repair", False)),
                        )
                    except ValueError as exc:
                        if "replayed" in str(exc):
                            replay_rejections += 1
                        else:
                            auth_failures += 1
                        server_to_client_bytes += await send_msg(writer, {"t": "ERROR", "error": str(exc)})
                        return
                    if outcome == "full":
                        full_frames += 1
                    elif outcome == "ref":
                        ref_frames += 1
                    elif outcome == "miss":
                        semantic_misses += 1
                    elif outcome == "repair":
                        repair_full_frames += 1
                    if first_reconstructed_byte_at is None and 0 in self.delivered:
                        first_reconstructed_byte_at = time.perf_counter()
                    if first_reconstructed_byte_at is not None and not first_byte_measurement_sent:
                        server_to_client_bytes += await send_msg(
                            writer, {"t": "FIRST_BYTE", "offset": 0},
                        )
                        first_byte_measurement_sent = True
                else:
                    server_to_client_bytes += await send_msg(writer, {"t": "ERROR", "error": f"unknown message {t}"})
                    return
        except asyncio.IncompleteReadError:
            return


class LossyUdpProxy(asyncio.DatagramProtocol):
    """Local UDP proxy that drops deterministic datagrams between QUIC endpoints."""
    def __init__(self, server_addr: tuple[str, int], *, loss_every: int = 0, shaper: Any = None):
        self.server_addr = server_addr
        self.loss_every = loss_every
        self.shaper = shaper  # optional userspace delay + token-bucket rate shaper
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
                self._forward(data, self.client_addr, direction="s2c")
        else:
            self.client_addr = addr
            self.c2s_seen += 1
            self.c2s_payload_bytes_seen += len(data)
            if self.loss_every and self.c2s_seen % self.loss_every == 0:
                self.c2s_dropped += 1
                return
            self.c2s_payload_bytes_forwarded += len(data)
            self._forward(data, self.server_addr, direction="c2s")

    def _forward(self, data: bytes, dest: tuple[str, int], *, direction: str = "c2s") -> None:
        if self.shaper is None:
            self.transport.sendto(data, dest)
            return
        deliver_at = self.shaper.schedule(len(data), direction=direction)
        transport = self.transport

        def _send() -> None:
            if transport is not None and not transport.is_closing():
                transport.sendto(data, dest)

        asyncio.get_event_loop().call_at(deliver_at, _send)

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
                    account_datagrams: bool = False, shaper: Any = None,
                    max_dict_chunks: int | None = None,
                    sender_max_dict_chunks: int | None = None,
                    receiver_max_dict_chunks: int | None = None,
                    server_port: int = 0, exporter_secret: bytes | None = None,
                    connection_context: bytes | None = None,
                    application_session_id: bytes | None = None,
                    expose_exporter_debug_hash: bool = False,
                    congestion_control_algorithm: str = "reno",
                    start_barrier: Any = None) -> dict[str, Any]:
    end_to_end_started = time.perf_counter()
    global WIRE_FORMAT
    WIRE_FORMAT = wire_format
    if exporter_secret is not None and not exporter_secret:
        raise ValueError("exporter secret override must not be empty")
    if connection_context is not None and application_session_id is not None:
        raise ValueError("provide connection_context or application_session_id, not both")
    if max_dict_chunks is not None:
        if sender_max_dict_chunks is not None or receiver_max_dict_chunks is not None:
            raise ValueError("max_dict_chunks cannot be combined with endpoint-specific budgets")
        sender_max_dict_chunks = max_dict_chunks
        receiver_max_dict_chunks = max_dict_chunks
    sender_max_dict_chunks = sender_max_dict_chunks or redulink.MAX_DICT_CHUNKS
    receiver_max_dict_chunks = receiver_max_dict_chunks or redulink.MAX_DICT_CHUNKS
    if sender_max_dict_chunks < 1 or receiver_max_dict_chunks < 1:
        raise ValueError("dictionary budgets must be positive")
    epoch = 7
    scope = "artifact-aioquic"
    if connection_context is not None:
        if not connection_context:
            raise ValueError("connection context must not be empty")
        client_connection_context = bytes(connection_context)
        server_connection_context = bytes(connection_context)
        connection_context_derivation = "caller-supplied endpoint-shared context"
    else:
        if application_session_id is None:
            application_session_id = secrets.token_bytes(32)
        if not application_session_id:
            raise ValueError("application session id must not be empty")
        # Invoke the endpoint-independent derivation separately for each role.
        client_connection_context = key_schedule.derive_connection_context(
            alpn=ALPN[0], application_session_id=application_session_id,
        )
        server_connection_context = key_schedule.derive_connection_context(
            alpn=ALPN[0], application_session_id=application_session_id,
        )
        connection_context_derivation = (
            "SHA-256 over versioned, length-prefixed ALPN and per-run "
            "authenticated application session id"
        )
    if not hmac.compare_digest(client_connection_context, server_connection_context):
        raise ValueError("client and server connection contexts differ")
    exporter_context = key_schedule.tls_exporter_context(
        alpn=ALPN[0], scope=scope,
        connection_context=client_connection_context,
    )

    def stream_secret(
        stream_id: int,
        endpoint_connection_context: bytes,
        endpoint_exporter_output: bytes,
    ) -> bytes:
        if stream_id < 0 or stream_id > wire.MAX_QUIC_STREAM_ID:
            raise ValueError("application stream id is outside the QUIC range")
        return key_schedule.derive_redulink_secret(
            endpoint_exporter_output,
            key_schedule.ReduLinkKeyContext(
                alpn=ALPN[0],
                epoch=epoch,
                scope=scope,
                connection_context=endpoint_connection_context,
                stream_context=stream_id.to_bytes(8, "big"),
                direction="client-to-server",
            ),
        )

    with tempfile.TemporaryDirectory(prefix="redulink-aioquic-") as tmp:
        cert_path, key_path = write_self_signed_cert(Path(tmp))
        server_conf = QuicConfiguration(is_client=False, alpn_protocols=ALPN)
        server_conf.congestion_control_algorithm = congestion_control_algorithm
        server_conf.load_cert_chain(str(cert_path), str(key_path))
        client_conf = QuicConfiguration(is_client=True, alpn_protocols=ALPN)
        client_conf.congestion_control_algorithm = congestion_control_algorithm
        client_conf.verify_mode = ssl.CERT_REQUIRED
        client_conf.cafile = str(cert_path)

        def stream_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            actual_stream_id = int(writer.get_extra_info("stream_id"))
            server_exporter_output = (
                bytes(exporter_secret)
                if exporter_secret is not None
                else tls_exporter.export_keying_material(
                    tls_exporter.tls_context_from_stream_writer(writer),
                    context_value=exporter_context,
                    length=key_schedule.HASH_LEN,
                )
            )
            server_state = QuicReduLinkServer(
                warm=warm,
                expected_sha256=hashlib.sha256(data).hexdigest(),
                expected_length=len(data),
                secret=stream_secret(
                    actual_stream_id,
                    server_connection_context,
                    server_exporter_output,
                ),
                epoch=epoch,
                scope=scope,
                stream_id=actual_stream_id,
                chunker="fixed",
                chunk_size=chunk_size,
                missing_every=missing_every,
                max_dict_chunks=receiver_max_dict_chunks,
                tls_exporter_output_sha256=hashlib.sha256(
                    server_exporter_output,
                ).hexdigest(),
            )
            asyncio.create_task(server_state.handle_stream(reader, writer))

        server = await serve("127.0.0.1", server_port, configuration=server_conf, stream_handler=stream_handler)
        assert server._transport is not None  # aioquic server exposes the bound datagram transport
        server_port = int(server._transport.get_extra_info("sockname")[1])
        proxy_transport = None
        proxy_protocol = None
        if loss_every > 0 or account_datagrams or shaper is not None:
            loop = asyncio.get_running_loop()
            proxy_protocol = LossyUdpProxy(("127.0.0.1", server_port), loss_every=loss_every, shaper=shaper)
            proxy_transport, _ = await loop.create_datagram_endpoint(lambda: proxy_protocol, local_addr=("127.0.0.1", 0))
            port = int(proxy_transport.get_extra_info("sockname")[1])
        else:
            port = server_port
        client_to_server_bytes = 0
        server_to_client_bytes = 0
        repaired = 0
        preparation_elapsed = 0.0
        diagnostic_stats_bytes = 0
        measurement_control_bytes = 0
        client_first_byte_at: float | None = None
        network_started = time.perf_counter()
        process_cpu_started = time.process_time()
        application_transfer_started = network_started
        application_completed = network_started
        process_cpu_completed = process_cpu_started
        try:
            async with connect("127.0.0.1", port, configuration=client_conf, wait_connected=True) as protocol:
                reader, writer = await protocol.create_stream()
                stream_id = int(writer.get_extra_info("stream_id"))
                response_queue: asyncio.Queue[tuple[dict[str, Any], int, float] | BaseException] = asyncio.Queue()

                async def collect_responses() -> None:
                    try:
                        while True:
                            response, response_size = await read_msg(reader)
                            await response_queue.put(
                                (response, response_size, time.perf_counter()),
                            )
                            if response.get("t") in {"STATS", "ERROR"}:
                                return
                    except BaseException as exc:
                        await response_queue.put(exc)

                async def next_response() -> tuple[dict[str, Any], int, float]:
                    item = await response_queue.get()
                    if isinstance(item, BaseException):
                        raise item
                    return item

                response_task = asyncio.create_task(collect_responses())
                client_exporter_output = (
                    bytes(exporter_secret)
                    if exporter_secret is not None
                    else tls_exporter.export_keying_material(
                        tls_exporter.tls_context_from_protocol(protocol),
                        context_value=exporter_context,
                        length=key_schedule.HASH_LEN,
                    )
                )
                client_exporter_output_sha256 = hashlib.sha256(
                    client_exporter_output,
                ).hexdigest()
                secret = stream_secret(
                    stream_id,
                    client_connection_context,
                    client_exporter_output,
                )
                preparation_started = time.perf_counter()
                frames, initial = secure.encode(
                    data,
                    warm_dictionary=warm,
                    secret=secret,
                    epoch=epoch,
                    scope=scope,
                    stream_id=stream_id,
                    chunker="fixed",
                    chunk_size=chunk_size,
                    max_dict_chunks=sender_max_dict_chunks,
                )
                sender_dict = build_secure_dictionary(
                    warm,
                    secret=secret,
                    epoch=epoch,
                    scope=scope,
                    chunker="fixed",
                    chunk_size=chunk_size,
                    max_dict_chunks=sender_max_dict_chunks,
                )
                preparation_elapsed = (time.perf_counter() - preparation_started) * 1000.0
                if start_barrier is not None:
                    await start_barrier.wait()
                application_transfer_started = time.perf_counter()
                client_to_server_bytes += await send_msg(writer, {
                    "t": "HELLO",
                    "version": PROTOCOL_VERSION,
                    "input_sha256": hashlib.sha256(data).hexdigest(),
                    "input_length": len(data),
                    "chunk_size": chunk_size,
                    "frame_count": len(frames),
                })
                client_to_server_bytes += await send_msgs_batched(
                    writer,
                    (frame_to_msg(seq, frame) for seq, frame in enumerate(frames)),
                )
                client_to_server_bytes += await send_msg(writer, {"t": "END_ROUND"})
                missing_items: list[dict[str, Any]] | None = None
                while missing_items is None:
                    reply, size, received_at = await next_response()
                    server_to_client_bytes += size
                    if reply.get("t") == "FIRST_BYTE":
                        if int(reply.get("offset", -1)) != 0 or client_first_byte_at is not None:
                            raise RuntimeError("invalid or duplicate FIRST_BYTE measurement")
                        client_first_byte_at = received_at
                        measurement_control_bytes += size
                    elif reply.get("t") == "MISSING":
                        missing_items = list(reply.get("items", []))
                    elif reply.get("t") == "ERROR":
                        raise RuntimeError(f"server rejected initial round: {reply.get('error', 'error')}")
                    else:
                        raise RuntimeError(f"unexpected server message before repair: {reply!r}")
                next_nonce = max((frame.nonce for frame in frames), default=0) + 1
                validated_repairs = validate_missing_items(missing_items, frames)
                repair_messages = []
                for seq, ref in validated_repairs:
                    payload = sender_dict.get(ref.cid)
                    if payload is None:
                        raise RuntimeError(f"sender has no repair payload for seq={seq}")
                    repair = make_full_repair(ref, payload, secret=secret, nonce=next_nonce)
                    next_nonce += 1
                    repaired += 1
                    repair_messages.append(frame_to_msg(seq, repair, repair=True))
                client_to_server_bytes += await send_msgs_batched(writer, repair_messages)
                client_to_server_bytes += await send_msg(writer, {"t": "FINISH"})
                stats: dict[str, Any] | None = None
                while stats is None:
                    reply, size, received_at = await next_response()
                    server_to_client_bytes += size
                    if reply.get("t") == "FIRST_BYTE":
                        if int(reply.get("offset", -1)) != 0 or client_first_byte_at is not None:
                            raise RuntimeError("invalid or duplicate FIRST_BYTE measurement")
                        client_first_byte_at = received_at
                        measurement_control_bytes += size
                    elif reply.get("t") == "ERROR":
                        raise RuntimeError(f"server rejected FINISH: {reply.get('error', 'error')}")
                    elif reply.get("t") == "STATS":
                        diagnostic_stats_bytes = size
                        stats = dict(reply["stats"])
                    else:
                        raise RuntimeError(f"unexpected server message after repair: {reply!r}")
                await response_task
                if client_first_byte_at is None:
                    raise RuntimeError("server never acknowledged logical byte zero")
                server_exporter_output_sha256 = str(
                    stats.pop("tls_exporter_output_sha256", ""),
                )
                tls_exporter_outputs_match = hmac.compare_digest(
                    client_exporter_output_sha256,
                    server_exporter_output_sha256,
                )
                if not tls_exporter_outputs_match:
                    raise RuntimeError("client and server TLS exporter outputs differ")
                if not bool(stats.get("reconstruction_ok")):
                    raise RuntimeError("server did not confirm exact reconstruction")
                if int(stats.get("application_stream_id", -1)) != stream_id:
                    raise RuntimeError("client/server application stream context mismatch")
                application_completed = time.perf_counter()
                process_cpu_completed = time.process_time()
                try:
                    writer.write_eof()
                    await writer.drain()
                except Exception:
                    pass
                writer.close()
                protocol.close()
        finally:
            if proxy_transport is not None:
                proxy_transport.close()
            server.close()

    network_elapsed = round((application_completed - network_started) * 1000.0, 3)
    end_to_end_elapsed = round((application_completed - end_to_end_started) * 1000.0, 3)
    setup_elapsed = round((network_started - end_to_end_started) * 1000.0, 3)
    process_cpu_elapsed = round((process_cpu_completed - process_cpu_started) * 1000.0, 3)
    protocol_reverse_bytes = (
        server_to_client_bytes - diagnostic_stats_bytes - measurement_control_bytes
    )
    protocol_stream_total = client_to_server_bytes + protocol_reverse_bytes
    stats.update({
        "input_bytes": len(data),
        "initial_redulink_model_wire_bytes": initial.wire_bytes,
        "initial_redulink_model_multiplier": round(initial.effective_multiplier, 6),
        "client_full_frames_initial": initial.full_frames,
        "client_ref_frames_initial": initial.ref_frames,
        "client_repair_full_frames_sent": repaired,
        "client_to_server_stream_payload_bytes_observed": client_to_server_bytes,
        "server_to_client_stream_payload_bytes_observed": server_to_client_bytes,
        "forward_protocol_stream_bytes": client_to_server_bytes,
        "reverse_repair_control_stream_bytes": protocol_reverse_bytes,
        "diagnostic_stats_stream_bytes": diagnostic_stats_bytes,
        "measurement_control_stream_bytes_excluded": measurement_control_bytes,
        "protocol_stream_payload_total_bytes_excluding_diagnostics": protocol_stream_total,
        "quic_stream_payload_total_bytes": protocol_stream_total,
        "quic_stream_payload_multiplier_after_repair": round(len(data) / protocol_stream_total, 6) if protocol_stream_total else 0,
        "client_elapsed_ms": network_elapsed,
        "client_network_elapsed_ms": network_elapsed,
        "client_time_to_first_reconstructed_byte_ms": round(
            ((client_first_byte_at or application_completed) - network_started) * 1000.0,
            3,
        ),
        "client_ttfb_definition": (
            "single client monotonic clock from immediately before connect to receipt of "
            "a byte-accounted application acknowledgement that logical offset zero is usable"
        ),
        "client_end_to_end_elapsed_ms": end_to_end_elapsed,
        "client_application_transfer_elapsed_ms": round(
            (application_completed - application_transfer_started) * 1000.0, 3,
        ),
        "client_application_time_to_first_reconstructed_byte_ms": round(
            ((client_first_byte_at or application_completed) - application_transfer_started) * 1000.0,
            3,
        ),
        "application_transfer_timing_definition": (
            "client monotonic clock from the first application-stream write boundary, after "
            "exporter-based preparation and any optional synchronization barrier, to FIRST_BYTE "
            "acknowledgement or completion"
        ),
        "client_preparation_elapsed_ms": round(preparation_elapsed, 3),
        "environment_setup_elapsed_ms": setup_elapsed,
        "combined_endpoint_process_cpu_ms": process_cpu_elapsed,
        "combined_endpoint_process_cpu_ms_per_mib": round(
            process_cpu_elapsed / (len(data) / (1024 * 1024)), 6,
        ) if data else 0.0,
        "process_cpu_definition": (
            "process_time delta covering the in-process client and server from immediately "
            "before connect through receipt of the final application result"
        ),
        "client_timing_definition": (
            "connection-and-application timing starts immediately before connect and stops after decoding "
            "the diagnostic STATS message; preparation is the in-connection frame and dictionary construction time"
        ),
        "stream_accounting_definition": (
            "protocol stream bytes include HELLO, data frames, END_ROUND, MISSING, repairs, and FINISH; "
            "the diagnostic STATS response and FIRST_BYTE measurement acknowledgement are reported "
            "separately and excluded from the multiplier"
        ),
        "aioquic_version": __import__("aioquic").__version__,
        "wire_format": WIRE_FORMAT,
        "datagram_loss_proxy_enabled": loss_every > 0,
        "datagram_loss_every": loss_every,
        "tls_server_certificate_verified": True,
        "tls_client_certificate_used": False,
        "connection_context_sha256": hashlib.sha256(client_connection_context).hexdigest(),
        "connection_contexts_match": hmac.compare_digest(
            client_connection_context, server_connection_context,
        ),
        "connection_context_derivation": connection_context_derivation,
        "tls_exporter_label": key_schedule.DEFAULT_LABEL.decode("ascii"),
        "tls_exporter_context_sha256": hashlib.sha256(exporter_context).hexdigest(),
        "tls_exporter_output_bytes": key_schedule.HASH_LEN,
        "tls_exporter_live": exporter_secret is None,
        "tls_exporter_outputs_match": tls_exporter_outputs_match,
        "tls_exporter_bridge": tls_exporter.bridge_description(),
        "tls_exporter_invocation": (
            "TLS-Exporter(label=EXPERIMENTAL-ReduLink-v1, "
            "context=SHA-256(versioned length-prefixed ALPN, scope, and connection context), "
            "length=32)"
        ),
        "record_mac_transcript": (
            "versioned fixed binary fields in network byte order; "
            "docs/protocol_test_vectors.json fixes bytes and outputs"
        ),
        "redulink_key_derivation": (
            "live TLS 1.3 exporter output plus canonical endpoint-independent "
            "connection, stream, direction, scope, and epoch context"
            if exporter_secret is None else
            "explicit test-only exporter override plus canonical endpoint-independent "
            "connection, stream, direction, scope, and epoch context"
        ),
        "sender_dictionary_budget_chunks": sender_max_dict_chunks,
        "receiver_dictionary_budget_chunks": receiver_max_dict_chunks,
        "receiver_dictionary_thinning_every": missing_every,
        "chunk_size_bytes": chunk_size,
        "sender_drain_batch_bytes": SEND_DRAIN_BYTES,
        "congestion_control_algorithm": congestion_control_algorithm,
    })
    if expose_exporter_debug_hash:
        stats["tls_exporter_output_sha256"] = client_exporter_output_sha256
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
                   account_datagrams: bool = False, max_dict_chunks: int | None = None,
                   sender_max_dict_chunks: int | None = None,
                   receiver_max_dict_chunks: int | None = None,
                   server_port: int = 0,
                   expose_exporter_debug_hash: bool = False,
                   congestion_control_algorithm: str = "reno") -> dict[str, Any]:
    warm, data = demo_payload(payload_blocks)
    return asyncio.run(run_async(
        warm=warm,
        data=data,
        chunk_size=chunk_size,
        missing_every=missing_every,
        wire_format=wire_format,
        loss_every=loss_every,
        account_datagrams=account_datagrams,
        max_dict_chunks=max_dict_chunks,
        sender_max_dict_chunks=sender_max_dict_chunks,
        receiver_max_dict_chunks=receiver_max_dict_chunks,
        server_port=server_port,
        expose_exporter_debug_hash=expose_exporter_debug_hash,
        congestion_control_algorithm=congestion_control_algorithm,
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
