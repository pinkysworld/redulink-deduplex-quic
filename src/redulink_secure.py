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
import heapq
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
DEFAULT_MAX_RECONSTRUCTED_BYTES = 64 * 1024 * 1024
CID_TRANSCRIPT_FORMAT = b"ReduLink CID transcript\x00\x01"
FRAME_TRANSCRIPT_FORMAT = b"ReduLink frame transcript\x00\x01"
KIND_CODE = {"FULL": 1, "REF": 2}
MAX_U32 = (1 << 32) - 1
MAX_U64 = (1 << 64) - 1


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


def _uint(name: str, value: int, width: int) -> bytes:
    maximum = MAX_U32 if width == 4 else MAX_U64
    number = int(value)
    if number < 0 or number > maximum:
        raise ValueError(f"{name} must fit an unsigned {width * 8}-bit integer")
    return number.to_bytes(width, "big")


def _length_prefixed(name: str, value: bytes) -> bytes:
    if len(value) > MAX_U32:
        raise ValueError(f"{name} is too long")
    return len(value).to_bytes(4, "big") + value


def cid_transcript(chunk: bytes, *, epoch: int, scope: str) -> bytes:
    """Return the versioned, endpoint-independent CID MAC transcript."""

    scope_bytes = scope.encode("utf-8")
    if not scope_bytes:
        raise ValueError("scope must not be empty")
    return (
        CID_TRANSCRIPT_FORMAT
        + _uint("epoch", epoch, 8)
        + _length_prefixed("scope", scope_bytes)
        + hashlib.sha256(chunk).digest()
    )


def frame_transcript(*, kind: str, epoch: int, scope: str, stream_id: int,
                     offset: int, cid: str, length: int, nonce: int,
                     payload: bytes) -> bytes:
    """Return the versioned, fixed-width frame MAC transcript.

    Integer fields use network byte order. Text and binary variable-length
    fields are length-prefixed. The CID is exactly 16 bytes and the payload is
    represented by its 32-byte SHA-256 digest. This encoding is independent of
    Python object or JSON serialization behavior.
    """

    if kind not in KIND_CODE:
        raise ValueError(f"unsupported frame kind: {kind}")
    scope_bytes = scope.encode("utf-8")
    if not scope_bytes:
        raise ValueError("scope must not be empty")
    try:
        cid_bytes = bytes.fromhex(cid)
    except ValueError as exc:
        raise ValueError("cid must be hexadecimal") from exc
    if len(cid_bytes) != CID_HEX_CHARS // 2:
        raise ValueError("cid must be 16 bytes / 32 hex characters")
    return (
        FRAME_TRANSCRIPT_FORMAT
        + bytes([KIND_CODE[kind]])
        + _uint("epoch", epoch, 8)
        + _length_prefixed("scope", scope_bytes)
        + _uint("stream_id", stream_id, 8)
        + _uint("offset", offset, 8)
        + cid_bytes
        + _uint("length", length, 4)
        + _uint("nonce", nonce, 8)
        + hashlib.sha256(payload).digest()
    )


def secure_cid(chunk: bytes, *, secret: bytes, epoch: int, scope: str) -> str:
    transcript = cid_transcript(chunk, epoch=epoch, scope=scope)
    return hmac.new(secret, transcript, hashlib.sha256).digest()[:TAG_BYTES].hex()


def frame_tag(*, secret: bytes, kind: str, epoch: int, scope: str, stream_id: int,
              offset: int, cid: str, length: int, nonce: int, payload: bytes) -> str:
    transcript = frame_transcript(
        kind=kind,
        epoch=epoch,
        scope=scope,
        stream_id=stream_id,
        offset=offset,
        cid=cid,
        length=length,
        nonce=nonce,
        payload=payload,
    )
    return hmac.new(secret, transcript, hashlib.sha256).digest()[:TAG_BYTES].hex()


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
            redulink.touch_lru(dictionary, c, dictionary[c], max_dict_chunks)
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


class NonceWindow:
    """Bounded, reorder-tolerant replay state (drop-in for a plain set).

    Keeps at most ``size`` recent nonces. A nonce is treated as replayed if it
    was already seen or if it falls below the sliding window floor, so memory
    is bounded for long-lived receivers while moderate datagram reordering
    inside the window remains accepted. Implements ``__contains__`` and
    ``add`` so existing callers that used a set keep working unchanged.
    """

    def __init__(self, size: int = 4096) -> None:
        self.size = int(size)
        if self.size < 1:
            raise ValueError("nonce window size must be positive")
        self.highest = 0
        self._seen: set[int] = set()
        self._min_heap: list[int] = []

    def __contains__(self, nonce: int) -> bool:
        if self.highest and nonce <= self.highest - self.size:
            return True  # below window floor: treat as replayed (fail closed)
        return nonce in self._seen

    def add(self, nonce: int) -> None:
        if nonce in self._seen:
            return
        self._seen.add(nonce)
        heapq.heappush(self._min_heap, nonce)
        if nonce > self.highest:
            self.highest = nonce
        floor = self.highest - self.size
        while self._min_heap and self._min_heap[0] <= floor:
            self._seen.discard(heapq.heappop(self._min_heap))

    def __len__(self) -> int:
        return len(self._seen)


def verify_frame(frame: SecureFrame, *, secret: bytes, expected_epoch: int, expected_scope: str,
                 expected_stream_id: int, expected_offset: int, seen_nonces) -> None:
    """Validate a frame: authentication first, then context, then replay.

    The MAC is checked before any context field so that an attacker without
    the key observes a single generic failure ("frame authentication failed")
    regardless of which field was tampered with; context mismatches are only
    distinguishable for authentically-tagged frames (i.e. cross-context replay
    of legitimate traffic). ``seen_nonces`` may be a plain set or a
    :class:`NonceWindow`.
    """
    if len(frame.tag) != TAG_BYTES * 2 or len(frame.cid) != CID_HEX_CHARS:
        raise ValueError("frame authentication failed")
    try:
        expected_tag = frame_tag(
            secret=secret, kind=frame.kind, epoch=frame.epoch, scope=frame.scope,
            stream_id=frame.stream_id, offset=frame.offset, cid=frame.cid,
            length=frame.length, nonce=frame.nonce, payload=frame.payload,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("frame authentication failed") from exc
    if not hmac.compare_digest(frame.tag, expected_tag):
        raise ValueError("frame authentication failed")
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


def decode(frames: Iterable[SecureFrame], *, warm_dictionary: bytes = b"",
           secret: bytes = DEFAULT_SECRET, epoch: int = 1, scope: str = DEFAULT_SCOPE,
           stream_id: int = 0, chunker: str = "fixed", chunk_size: int = redulink.DEFAULT_CHUNK,
           max_dict_chunks: int = redulink.MAX_DICT_CHUNKS,
           max_reconstructed_bytes: int = DEFAULT_MAX_RECONSTRUCTED_BYTES) -> bytes:
    if max_reconstructed_bytes < 0:
        raise ValueError("max_reconstructed_bytes must be non-negative")
    dictionary = _dictionary_from_bytes(
        warm_dictionary, secret=secret, epoch=epoch, scope=scope,
        chunker=chunker, chunk_size=chunk_size, max_dict_chunks=max_dict_chunks,
    )
    seen_nonces = NonceWindow()
    output: List[bytes] = []
    expected_offset = 0
    for frame in frames:
        if frame.length <= 0 or frame.length > max(chunk_size, 32768 if chunker == "cdc" else chunk_size):
            raise ValueError("frame length exceeds configured chunk bound")
        if expected_offset + frame.length > max_reconstructed_bytes:
            raise ValueError("reconstructed byte limit exceeded")
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
            if secure_cid(chunk, secret=secret, epoch=epoch, scope=scope) != frame.cid:
                raise ValueError("REF dictionary chunk id mismatch")
            redulink.touch_lru(dictionary, frame.cid, chunk, max_dict_chunks)
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
