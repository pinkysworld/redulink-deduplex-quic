#!/usr/bin/env python3
"""Compact binary ReduLink stream-mapping wire format.

The first aioquic artifact carried ReduLink frames as length-prefixed JSON so
reviewers could inspect every field. This module adds a compact binary mapping
for the same message sequence. It is still an application-stream mapping, not a
custom QUIC extension-frame parser, but it removes base64 and JSON overhead from
native QUIC experiments and makes the measured stream bytes closer to the
protocol sketch in the paper.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from typing import Any

try:
    from .redulink_secure import SecureFrame
except Exception:  # pragma: no cover
    from redulink_secure import SecureFrame  # type: ignore

LEN_BYTES = 4
MAX_MESSAGE_BYTES = 16 * 1024 * 1024
HELLO = 1
END_ROUND = 2
MISSING = 3
FINISH = 4
STATS = 5
ERROR = 6
FRAME = 16
KIND_FULL = 1
KIND_REF = 2
KIND_BY_NAME = {"FULL": KIND_FULL, "REF": KIND_REF}
NAME_BY_KIND = {KIND_FULL: "FULL", KIND_REF: "REF"}
_HEADER = struct.Struct("!I")
_FRAME_FIXED = struct.Struct("!IBBHQQQQI16s16sI")
# seq:uint32 repair:uint8 kind:uint8 scope_len:uint16 epoch:uint64 stream_id:uint64
# offset:uint64 nonce:uint64 length:uint32 cid:16 tag:16 payload_len:uint32
_MISSING_HEADER = struct.Struct("!I")
_MISSING_ITEM = struct.Struct("!I16sI")
_HELLO_FIXED = struct.Struct("!HIIQ32s")
MAX_MISSING_ITEMS = (MAX_MESSAGE_BYTES - 1 - _MISSING_HEADER.size) // _MISSING_ITEM.size
MAX_QUIC_STREAM_ID = (1 << 62) - 1
MAX_QUIC_STREAM_OFFSET = (1 << 62) - 1


def _bounded_int(name: str, value: Any, maximum: int) -> int:
    number = int(value)
    if number < 0 or number > maximum:
        raise ValueError(f"{name} must be between 0 and {maximum}")
    return number


@dataclass(frozen=True)
class DecodedMessage:
    t: str
    obj: dict[str, Any]


def _cid_bytes(cid: str) -> bytes:
    raw = bytes.fromhex(cid)
    if len(raw) != 16:
        raise ValueError("cid must be 16 bytes / 32 hex characters")
    return raw


def _tag_bytes(tag: str) -> bytes:
    raw = bytes.fromhex(tag)
    if len(raw) != 16:
        raise ValueError("tag must be 16 bytes / 32 hex characters")
    return raw


def encode_message(obj: dict[str, Any]) -> bytes:
    t = obj.get("t")
    if t == "HELLO":
        body = bytes([HELLO]) + _HELLO_FIXED.pack(
            int(obj.get("version", 1)),
            int(obj["chunk_size"]),
            int(obj["frame_count"]),
            _bounded_int("input length", obj["input_length"], MAX_QUIC_STREAM_OFFSET),
            bytes.fromhex(str(obj["input_sha256"])),
        )
    elif t == "END_ROUND":
        body = bytes([END_ROUND])
    elif t == "FINISH":
        body = bytes([FINISH])
    elif t == "FRAME":
        frame = obj["frame"]
        if not isinstance(frame, SecureFrame):
            raise TypeError("FRAME messages require a SecureFrame under key 'frame'")
        scope = frame.scope.encode("utf-8")
        if len(scope) > 65535:
            raise ValueError("scope too long")
        body = (
            bytes([FRAME])
            + _FRAME_FIXED.pack(
                _bounded_int("seq", obj["seq"], (1 << 32) - 1),
                1 if bool(obj.get("repair", False)) else 0,
                KIND_BY_NAME[frame.kind],
                len(scope),
                _bounded_int("epoch", frame.epoch, (1 << 64) - 1),
                _bounded_int("stream_id", frame.stream_id, MAX_QUIC_STREAM_ID),
                _bounded_int("offset", frame.offset, MAX_QUIC_STREAM_OFFSET),
                _bounded_int("nonce", frame.nonce, (1 << 64) - 1),
                _bounded_int("length", frame.length, (1 << 32) - 1),
                _cid_bytes(frame.cid),
                _tag_bytes(frame.tag),
                _bounded_int("payload length", len(frame.payload), (1 << 32) - 1),
            )
            + scope
            + frame.payload
        )
    elif t == "MISSING":
        items = list(obj.get("items", []))
        if len(items) > MAX_MISSING_ITEMS:
            raise ValueError(f"MISSING item count exceeds {MAX_MISSING_ITEMS}")
        body_buffer = bytearray(bytes([MISSING]) + _MISSING_HEADER.pack(len(items)))
        for item in items:
            body_buffer.extend(
                _MISSING_ITEM.pack(
                    _bounded_int("missing seq", item["seq"], (1 << 32) - 1),
                    _cid_bytes(str(item["cid"])),
                    _bounded_int("missing length", item["length"], (1 << 32) - 1),
                )
            )
        body = bytes(body_buffer)
    elif t == "STATS":
        payload = json.dumps(obj["stats"], sort_keys=True, separators=(",", ":")).encode("utf-8")
        body = bytes([STATS]) + payload
    elif t == "ERROR":
        payload = str(obj.get("error", "error")).encode("utf-8")
        body = bytes([ERROR]) + payload
    else:
        raise ValueError(f"unsupported message type: {t}")
    if not body or len(body) > MAX_MESSAGE_BYTES:
        raise ValueError(f"message length must be between 1 and {MAX_MESSAGE_BYTES} bytes")
    return _HEADER.pack(len(body)) + body


def decode_payload(body: bytes) -> DecodedMessage:
    if not body:
        raise ValueError("empty binary ReduLink message")
    mt = body[0]
    data = body[1:]
    if mt == HELLO:
        if len(data) != _HELLO_FIXED.size:
            raise ValueError("invalid HELLO length")
        version, chunk_size, frame_count, input_length, digest = _HELLO_FIXED.unpack(data)
        return DecodedMessage("HELLO", {
            "t": "HELLO",
            "version": version,
            "chunk_size": chunk_size,
            "frame_count": frame_count,
            "input_length": input_length,
            "input_sha256": digest.hex(),
        })
    if mt == END_ROUND:
        if data:
            raise ValueError("invalid END_ROUND length")
        return DecodedMessage("END_ROUND", {"t": "END_ROUND"})
    if mt == FINISH:
        if data:
            raise ValueError("invalid FINISH length")
        return DecodedMessage("FINISH", {"t": "FINISH"})
    if mt == FRAME:
        fixed_len = _FRAME_FIXED.size
        if len(data) < fixed_len:
            raise ValueError("truncated FRAME header")
        seq, repair, kind_id, scope_len, epoch, stream_id, offset, nonce, length, cid_b, tag_b, payload_len = _FRAME_FIXED.unpack(data[:fixed_len])
        if repair not in (0, 1):
            raise ValueError("invalid FRAME repair flag")
        if kind_id not in NAME_BY_KIND:
            raise ValueError("invalid FRAME kind")
        start = fixed_len
        end = start + scope_len
        message_end = end + payload_len
        if end > len(data):
            raise ValueError("truncated FRAME scope")
        scope = data[start:end].decode("utf-8")
        payload = data[end:message_end]
        if len(payload) != payload_len:
            raise ValueError("truncated FRAME payload")
        if message_end != len(data):
            raise ValueError("trailing bytes after FRAME")
        frame = SecureFrame(
            kind=NAME_BY_KIND[kind_id],
            epoch=epoch,
            scope=scope,
            stream_id=stream_id,
            offset=offset,
            cid=cid_b.hex(),
            length=length,
            nonce=nonce,
            tag=tag_b.hex(),
            payload=payload,
        )
        return DecodedMessage("FRAME", {"t": "FRAME", "seq": seq, "repair": bool(repair), "frame": frame})
    if mt == MISSING:
        if len(data) < _MISSING_HEADER.size:
            raise ValueError("truncated MISSING header")
        count = _MISSING_HEADER.unpack(data[:_MISSING_HEADER.size])[0]
        if count > MAX_MISSING_ITEMS:
            raise ValueError("MISSING item count exceeds message bound")
        expected_len = _MISSING_HEADER.size + count * _MISSING_ITEM.size
        if len(data) != expected_len:
            raise ValueError("invalid MISSING length")
        pos = _MISSING_HEADER.size
        items = []
        for _ in range(count):
            seq, cid_b, length = _MISSING_ITEM.unpack(data[pos:pos + _MISSING_ITEM.size])
            pos += _MISSING_ITEM.size
            items.append({"seq": seq, "cid": cid_b.hex(), "length": length})
        return DecodedMessage("MISSING", {"t": "MISSING", "items": items})
    if mt == STATS:
        return DecodedMessage("STATS", {"t": "STATS", "stats": json.loads(data.decode("utf-8"))})
    if mt == ERROR:
        return DecodedMessage("ERROR", {"t": "ERROR", "error": data.decode("utf-8", "replace")})
    raise ValueError(f"unknown binary ReduLink message type: {mt}")


async def send_message(writer: Any, obj: dict[str, Any]) -> int:
    data = encode_message(obj)
    writer.write(data)
    await writer.drain()
    return len(data)


async def read_message(reader: Any) -> tuple[dict[str, Any], int]:
    header = await reader.readexactly(LEN_BYTES)
    length = int.from_bytes(header, "big")
    if length < 1 or length > MAX_MESSAGE_BYTES:
        raise ValueError(f"message length must be between 1 and {MAX_MESSAGE_BYTES} bytes")
    body = await reader.readexactly(length)
    decoded = decode_payload(body)
    return decoded.obj, LEN_BYTES + length
