#!/usr/bin/env python3
"""Exporter-style ReduLink key schedule for artifact experiments.

Production Deduplex-QUIC should derive ReduLink authentication keys from a QUIC
TLS exporter. The public artifact cannot depend on private QUIC stack internals,
so it implements the same style of context-separated derivation using HKDF over
an explicit master secret and transport context. This lets tests verify that
ReduLink frame keys change when ALPN, connection context, epoch, or dictionary
scope changes.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

HASH_LEN = 32
DEFAULT_LABEL = b"EXPORTER-ReduLink-v1"


@dataclass(frozen=True)
class ReduLinkKeyContext:
    alpn: str
    epoch: int
    scope: str
    connection_context: bytes = b""
    stream_context: bytes = b""


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


def context_info(ctx: ReduLinkKeyContext, *, label: bytes = DEFAULT_LABEL) -> bytes:
    if ctx.epoch < 0:
        raise ValueError("epoch must be non-negative")
    parts = [
        label,
        b"alpn=" + ctx.alpn.encode("utf-8"),
        b"epoch=" + str(ctx.epoch).encode("ascii"),
        b"scope=" + ctx.scope.encode("utf-8"),
        b"conn=" + ctx.connection_context.hex().encode("ascii"),
        b"stream=" + ctx.stream_context.hex().encode("ascii"),
    ]
    return b"|".join(parts)


def derive_redulink_secret(master_secret: bytes, ctx: ReduLinkKeyContext, *, length: int = 32) -> bytes:
    """Derive a ReduLink frame-authentication secret from transport context.

    In a production QUIC implementation, ``master_secret`` would be replaced by
    bytes returned from a TLS exporter. In the artifact, callers pass a stable
    experiment secret and context fields; tests verify domain separation.
    """
    if not master_secret:
        raise ValueError("master_secret must not be empty")
    prk = hkdf_extract(DEFAULT_LABEL, master_secret)
    return hkdf_expand(prk, context_info(ctx), length)
