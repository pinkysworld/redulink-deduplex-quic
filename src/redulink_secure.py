#!/usr/bin/env python3
"""Authenticated ReduLink representation-layer model.

This module is intentionally small, but it implements the security-critical
bindings that the main paper specifies for a production transport profile:

* per-connection secret input;
* epoch and scope binding for chunk identifiers;
* stream id and reconstructed offset binding for reference tags;
* monotonically unique nonces and replay rejection;
* fail-closed handling for tag, length, offset, and dictionary mismatches.

It is not a QUIC implementation. It is a runnable artifact model for the
message-authentication and replay semantics expected from a Deduplex-QUIC
profile.
"""

from __future__ import annotations

import hmac
import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable, List, Tuple

try:  # script and package execution modes
    from . import redulink_model as redulink
except Exception:  # pragma: no cover
    import redulink_model as redulink  # type: ignore

TAG_BYTES = 16
CID_HEX_CHARS = 32
DEFAULT_SECRET = b"redulink-artifact-secret-for-tests-only"
DEFAULT_SCOPE = "per-connection-artifact-scope"


@dataclass(frozen=True)
class SecureFrame:
    kind: str
    epoch: int
    scope: str
    stream_id: int
    offset: int
    cid: str
    length: int
    nonce: int
    tag: str
    payload: bytes = b""


@dataclass
class SecureStats:
    input_bytes: int
    wire_bytes: int
    chunks: int
    full_frames: int
    ref_frames: int
    saving_rate: float
    effective_multiplier: float
    reconstruction_ok: bool
    auth_failures: int = 0
    replay_rejections: int = 0


def _mac(secret: bytes, label: str, fields: dict[str, object]) -> bytes:
    encoded = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(secret, label.encode("ascii") + b"\0" + encoded, hashlib.sha256).digest()


def secure_cid(chunk: bytes, *, secret: bytes, epoch: int, scope: str) -> str:
    digest = hashlib.sha256(chunk).hexdigest()
    return _mac(secret, "cid", {"epoch": epoch, "scope": scope, "sha256": digest}).hex()[:CID_HEX_CHARS]


def frame_tag(*, secret: bytes, kind: str, epoch: int, scope: str, stream_id: int,
              offset: int, cid: str, length: int, nonce: int, payload: bytes) -> str:
    fields = {
        "kind": kind,
        "epoch": epoch,
        "scope": scope,
        "stream_id": stream_id,
        "offset": offset,
        "cid": cid,
        "length": length,
        "nonce": nonce,
        "payload_sha256": hashlib.sha256(payload).hexdigest() if payload else "",
    }
    return _mac(secret, "frame", fields)[:TAG_BYTES].hex()


def _dictionary_from_bytes(data: bytes, *, secret: bytes, epoch: int, scope: str,
                           chunker: str, chunk_size: int,
                           max_dict_chunks: int) -> OrderedDict[str, bytes]:
    dictionary: OrderedDict[str, bytes] = OrderedDict()
    for chunk in redulink.make_chunks(data, chunker, chunk_size):
        redulink.touch_lru(dictionary, secure_cid(chunk, secret=secret, epoch=epoch, scope=scope), chunk, max_dict_chunks)
    return dictionary


def _wire_size(frame: SecureFrame) -> int:
    # Conservative model: frame metadata includes extension type, epoch, stream id,
    # offset, length, nonce, truncated cid, tag, and varint overhead. FULL frames
    # additionally carry the original bytes.
    base = 56
    return base + len(frame.payload)


def encode(data: bytes, *, warm_dictionary: bytes = b"", secret: bytes = DEFAULT_SECRET,
           epoch: int = 1, scope: str = DEFAULT_SCOPE, stream_id: int = 0,
           chunker: str = "fixed", chunk_size: int = redulink.DEFAULT_CHUNK,
           max_dict_chunks: int = redulink.MAX_DICT_CHUNKS) -> Tuple[List[SecureFrame], SecureStats]:
    dictionary = _dictionary_from_bytes(
        warm_dictionary, secret=secret, epoch=epoch, scope=scope,
        chunker=chunker, chunk_size=chunk_size, max_dict_chunks=max_dict_chunks,
    )
    frames: List[SecureFrame] = []
    offset = 0
    full = 0
    ref = 0
    wire = 0
    nonce = 1
    for chunk in redulink.make_chunks(data, chunker, chunk_size):
        c = secure_cid(chunk, secret=secret, epoch=epoch, scope=scope)
        if c in dictionary:
            kind = "REF"
            payload = b""
            ref += 1
        else:
            kind = "FULL"
            payload = chunk
            full += 1
        tag = frame_tag(
            secret=secret, kind=kind, epoch=epoch, scope=scope, stream_id=stream_id,
            offset=offset, cid=c, length=len(chunk), nonce=nonce, payload=payload,
        )
        frame = SecureFrame(kind, epoch, scope, stream_id, offset, c, len(chunk), nonce, tag, payload)
        frames.append(frame)
        wire += _wire_size(frame)
        if kind == "FULL":
            redulink.touch_lru(dictionary, c, chunk, max_dict_chunks)
        offset += len(chunk)
        nonce += 1
    saving = max(0.0, 1.0 - wire / len(data)) if data else 0.0
    mult = (len(data) / wire) if wire else 1.0
    stats = SecureStats(len(data), wire, len(frames), full, ref, saving, mult, False)
    return frames, stats


def verify_frame(frame: SecureFrame, *, secret: bytes, expected_epoch: int, expected_scope: str,
                 expected_stream_id: int, expected_offset: int, seen_nonces: set[int]) -> None:
    if frame.epoch != expected_epoch:
        raise ValueError("epoch mismatch")
    if frame.scope != expected_scope:
        raise ValueError("scope mismatch")
    if frame.stream_id != expected_stream_id:
        raise ValueError("stream id mismatch")
    if frame.offset != expected_offset:
        raise ValueError("stream offset mismatch")
    if frame.nonce in seen_nonces:
        raise ValueError("replayed nonce")
    expected_tag = frame_tag(
        secret=secret, kind=frame.kind, epoch=frame.epoch, scope=frame.scope,
        stream_id=frame.stream_id, offset=frame.offset, cid=frame.cid,
        length=frame.length, nonce=frame.nonce, payload=frame.payload,
    )
    if not hmac.compare_digest(frame.tag, expected_tag):
        raise ValueError("frame authentication failed")


def decode(frames: Iterable[SecureFrame], *, warm_dictionary: bytes = b"",
           secret: bytes = DEFAULT_SECRET, epoch: int = 1, scope: str = DEFAULT_SCOPE,
           stream_id: int = 0, chunker: str = "fixed", chunk_size: int = redulink.DEFAULT_CHUNK,
           max_dict_chunks: int = redulink.MAX_DICT_CHUNKS) -> bytes:
    dictionary = _dictionary_from_bytes(
        warm_dictionary, secret=secret, epoch=epoch, scope=scope,
        chunker=chunker, chunk_size=chunk_size, max_dict_chunks=max_dict_chunks,
    )
    seen_nonces: set[int] = set()
    output: List[bytes] = []
    expected_offset = 0
    for frame in frames:
        verify_frame(
            frame, secret=secret, expected_epoch=epoch, expected_scope=scope,
            expected_stream_id=stream_id, expected_offset=expected_offset,
            seen_nonces=seen_nonces,
        )
        seen_nonces.add(frame.nonce)
        if frame.kind == "FULL":
            if len(frame.payload) != frame.length:
                raise ValueError("FULL length mismatch")
            if secure_cid(frame.payload, secret=secret, epoch=epoch, scope=scope) != frame.cid:
                raise ValueError("FULL chunk id mismatch")
            redulink.touch_lru(dictionary, frame.cid, frame.payload, max_dict_chunks)
            output.append(frame.payload)
        elif frame.kind == "REF":
            chunk = dictionary.get(frame.cid)
            if chunk is None:
                raise ValueError("REF miss")
            if len(chunk) != frame.length:
                raise ValueError("REF length mismatch")
            output.append(chunk)
        else:
            raise ValueError(f"unknown frame kind: {frame.kind}")
        expected_offset += frame.length
    return b"".join(output)


def run_bytes(data: bytes, *, warm_dictionary: bytes = b"", secret: bytes = DEFAULT_SECRET,
              epoch: int = 1, scope: str = DEFAULT_SCOPE, stream_id: int = 0,
              chunker: str = "fixed", chunk_size: int = redulink.DEFAULT_CHUNK) -> SecureStats:
    frames, stats = encode(
        data, warm_dictionary=warm_dictionary, secret=secret, epoch=epoch, scope=scope,
        stream_id=stream_id, chunker=chunker, chunk_size=chunk_size,
    )
    reconstructed = decode(
        frames, warm_dictionary=warm_dictionary, secret=secret, epoch=epoch, scope=scope,
        stream_id=stream_id, chunker=chunker, chunk_size=chunk_size,
    )
    stats.reconstruction_ok = reconstructed == data
    return stats
