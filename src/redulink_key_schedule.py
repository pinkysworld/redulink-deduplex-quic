#!/usr/bin/env python3
"""Context separation for ReduLink keys obtained from a TLS 1.3 exporter."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

HASH_LEN = 32
DEFAULT_LABEL = b"EXPERIMENTAL-ReduLink-v1"
CONTEXT_FORMAT = b"ReduLink key context\x00\x01"
CONNECTION_CONTEXT_FORMAT = b"ReduLink connection context\x00\x01"
TLS_EXPORTER_CONTEXT_FORMAT = b"ReduLink TLS exporter context\x00\x01"
MAX_CONTEXT_FIELD_BYTES = (1 << 32) - 1


@dataclass(frozen=True)
class ReduLinkKeyContext:
    alpn: str
    epoch: int
    scope: str
    connection_context: bytes = b""
    stream_context: bytes = b""
    direction: str = "client-to-server"


def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    if not salt:
        salt = b"\x00" * HASH_LEN
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    if length <= 0:
        raise ValueError("length must be positive")
    blocks = []
    previous = b""
    counter = 1
    while len(b"".join(blocks)) < length:
        previous = hmac.new(prk, previous + info + bytes([counter]), hashlib.sha256).digest()
        blocks.append(previous)
        counter += 1
        if counter > 255:
            raise ValueError("HKDF output too long")
    return b"".join(blocks)[:length]


def _length_prefixed(value: bytes) -> bytes:
    """Encode one context field without delimiter ambiguity."""

    if len(value) > MAX_CONTEXT_FIELD_BYTES:
        raise ValueError("context field is too long")
    return len(value).to_bytes(4, "big") + value


def derive_connection_context(*, alpn: str, application_session_id: bytes) -> bytes:
    """Derive the same 32-byte connection context at either endpoint.

    ``application_session_id`` must be an authenticated, endpoint-shared value
    established before ReduLink records are processed. It is generated once per
    artifact run; production deployments can bind an application transfer or
    synchronization-session identifier carried inside QUIC/TLS protection.
    """

    if not alpn:
        raise ValueError("alpn must not be empty")
    if not application_session_id:
        raise ValueError("application_session_id must not be empty")
    transcript = (
        CONNECTION_CONTEXT_FORMAT
        + _length_prefixed(alpn.encode("utf-8"))
        + _length_prefixed(application_session_id)
    )
    return hashlib.sha256(transcript).digest()


def tls_exporter_context(*, alpn: str, scope: str,
                         connection_context: bytes) -> bytes:
    """Return the exact 32-byte context for the live TLS exporter call.

    The production invocation is TLS-Exporter with label
    ``EXPERIMENTAL-ReduLink-v1``, this function's return value as ``context``,
    and output length 32 bytes. The ``EXPERIMENTAL`` prefix permits private use
    without IANA registration under RFC 5705. A nonexperimental deployment
    must register its label.
    """

    if not alpn:
        raise ValueError("alpn must not be empty")
    if not scope:
        raise ValueError("scope must not be empty")
    if not connection_context:
        raise ValueError("connection_context must not be empty")
    transcript = (
        TLS_EXPORTER_CONTEXT_FORMAT
        + _length_prefixed(alpn.encode("utf-8"))
        + _length_prefixed(scope.encode("utf-8"))
        + _length_prefixed(connection_context)
    )
    return hashlib.sha256(transcript).digest()


def context_info(ctx: ReduLinkKeyContext, *, label: bytes = DEFAULT_LABEL) -> bytes:
    """Return a canonical, injective binary encoding of the key context.

    Earlier artifact revisions joined textual fields with ``|`` delimiters.
    Delimiters inside ALPN or scope strings could therefore make distinct
    contexts collide. This version uses length-prefixed UTF-8/binary fields and
    a fixed-width epoch.
    """

    if not ctx.alpn:
        raise ValueError("alpn must not be empty")
    if not ctx.scope:
        raise ValueError("scope must not be empty")
    if not ctx.direction:
        raise ValueError("direction must not be empty")
    if ctx.epoch < 0 or ctx.epoch > (1 << 64) - 1:
        raise ValueError("epoch must fit an unsigned 64-bit integer")
    fields = (
        label,
        ctx.alpn.encode("utf-8"),
        ctx.scope.encode("utf-8"),
        ctx.connection_context,
        ctx.stream_context,
        ctx.direction.encode("utf-8"),
    )
    return CONTEXT_FORMAT + b"".join(_length_prefixed(field) for field in fields[:2]) + ctx.epoch.to_bytes(8, "big") + b"".join(
        _length_prefixed(field) for field in fields[2:]
    )


def derive_redulink_secret(master_secret: bytes, ctx: ReduLinkKeyContext, *, length: int = 32) -> bytes:
    """Derive a ReduLink frame-authentication secret from transport context.

    ``master_secret`` is the output of the live TLS exporter. This function is
    the subsequent ReduLink-specific HKDF/context-separation step.
    """
    if not master_secret:
        raise ValueError("master_secret must not be empty")
    prk = hkdf_extract(DEFAULT_LABEL, master_secret)
    return hkdf_expand(prk, context_info(ctx), length)
