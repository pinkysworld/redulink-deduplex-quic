#!/usr/bin/env python3
"""TLS 1.3 exporter bridge for the pinned aioquic artifact.

aioquic 1.3.0 does not expose TLS exporters through a public API.  Its TLS
state machine nevertheless reaches the RFC 9846 exporter derivation point at
the first 1-RTT traffic-key installation, after Server Finished is in the
transcript and after the master-secret extraction.  This module installs a
strictly version-gated hook at that point.

The hook does not retain the general exporter master secret.  It immediately
derives the label-specific ReduLink secret for the private-use exporter label,
then retains only that narrower value for context-specific expansion.  This
follows the erasure guidance in RFC 9846, Appendix F.1.4.
"""

from __future__ import annotations

from typing import Any

import aioquic
from aioquic import tls
from cryptography.hazmat.primitives import hashes

SUPPORTED_AIOQUIC_VERSION = "1.3.0"
EXPORTER_LABEL = b"EXPERIMENTAL-ReduLink-v1"
EXPORTER_OUTPUT_BYTES = 32
_LABEL_SECRET_ATTRIBUTE = "_redulink_exporter_label_secret"
_ALGORITHM_ATTRIBUTE = "_redulink_exporter_algorithm"
_BRIDGE_MARKER = "_redulink_exporter_bridge"


def _digest(algorithm: hashes.HashAlgorithm, value: bytes) -> bytes:
    digest = hashes.Hash(algorithm)
    digest.update(value)
    return digest.finalize()


def _validate_label(label: bytes) -> None:
    if not label:
        raise ValueError("TLS exporter label must not be empty")
    if b"\x00" in label or any(byte < 0x20 or byte > 0x7E for byte in label):
        raise ValueError("TLS exporter label must be printable ASCII without NUL")


def _derive_label_secret(
    *,
    exporter_master_secret: bytes,
    label: bytes,
    algorithm: hashes.HashAlgorithm,
) -> bytes:
    """Compute Derive-Secret(exporter_secret, label, "")."""

    _validate_label(label)
    if not exporter_master_secret:
        raise ValueError("exporter master secret must not be empty")
    return tls.hkdf_expand_label(
        algorithm=algorithm,
        secret=exporter_master_secret,
        label=label,
        hash_value=_digest(algorithm, b""),
        length=algorithm.digest_size,
    )


def export_keying_material_from_secret(
    *,
    exporter_master_secret: bytes,
    label: bytes,
    context_value: bytes,
    length: int,
    algorithm: hashes.HashAlgorithm | None = None,
) -> bytes:
    """Evaluate the RFC 9846 TLS-Exporter construction from a fixed secret.

    This pure helper supports public test vectors.  Live connections use
    :func:`export_keying_material`, which consumes the narrower label secret
    captured by the pinned aioquic bridge.
    """

    if length <= 0 or length > 65535:
        raise ValueError("TLS exporter length must be between 1 and 65535 bytes")
    algorithm = algorithm or hashes.SHA256()
    label_secret = _derive_label_secret(
        exporter_master_secret=exporter_master_secret,
        label=label,
        algorithm=algorithm,
    )
    return tls.hkdf_expand_label(
        algorithm=algorithm,
        secret=label_secret,
        label=b"exporter",
        hash_value=_digest(algorithm, context_value),
        length=length,
    )


def install_aioquic_exporter_bridge() -> None:
    """Install the audited aioquic 1.3.0 TLS exporter capture hook once."""

    if aioquic.__version__ != SUPPORTED_AIOQUIC_VERSION:
        raise RuntimeError(
            "ReduLink's TLS exporter bridge is audited only for aioquic "
            f"{SUPPORTED_AIOQUIC_VERSION}; found {aioquic.__version__}"
        )
    current = tls.Context._setup_traffic_protection
    if getattr(current, _BRIDGE_MARKER, False):
        return
    original = current

    def setup_traffic_protection(
        context: tls.Context,
        direction: tls.Direction,
        epoch: tls.Epoch,
        label: bytes,
    ) -> None:
        if (
            epoch == tls.Epoch.ONE_RTT
            and not hasattr(context, _LABEL_SECRET_ATTRIBUTE)
        ):
            if context.key_schedule.generation != 3:
                raise RuntimeError("unexpected aioquic TLS key-schedule generation")
            algorithm = context.key_schedule.algorithm
            exporter_master_secret = context.key_schedule.derive_secret(b"exp master")
            label_secret = _derive_label_secret(
                exporter_master_secret=exporter_master_secret,
                label=EXPORTER_LABEL,
                algorithm=algorithm,
            )
            setattr(context, _LABEL_SECRET_ATTRIBUTE, label_secret)
            setattr(context, _ALGORITHM_ATTRIBUTE, algorithm)
        original(context, direction, epoch, label)

    setattr(setup_traffic_protection, _BRIDGE_MARKER, True)
    tls.Context._setup_traffic_protection = setup_traffic_protection


def export_keying_material(
    context: tls.Context,
    *,
    context_value: bytes,
    length: int = EXPORTER_OUTPUT_BYTES,
) -> bytes:
    """Export ReduLink keying material from one completed live TLS context."""

    if length <= 0 or length > 65535:
        raise ValueError("TLS exporter length must be between 1 and 65535 bytes")
    try:
        label_secret = getattr(context, _LABEL_SECRET_ATTRIBUTE)
        algorithm = getattr(context, _ALGORITHM_ATTRIBUTE)
    except AttributeError as exc:
        raise RuntimeError(
            "TLS exporter material is unavailable; install the bridge before "
            "the handshake and wait for 1-RTT keys"
        ) from exc
    return tls.hkdf_expand_label(
        algorithm=algorithm,
        secret=label_secret,
        label=b"exporter",
        hash_value=_digest(algorithm, context_value),
        length=length,
    )


def tls_context_from_protocol(protocol: Any) -> tls.Context:
    """Return the live TLS context from the pinned aioquic protocol object."""

    connection = getattr(protocol, "_quic", None)
    context = getattr(connection, "tls", None)
    if context is None:
        raise RuntimeError("aioquic protocol does not expose a completed TLS context")
    return context


def tls_context_from_stream_writer(writer: Any) -> tls.Context:
    """Return the server-side TLS context associated with a QUIC stream."""

    transport = getattr(writer, "transport", None)
    protocol = getattr(transport, "protocol", None)
    if protocol is None:
        raise RuntimeError("stream writer is not backed by an aioquic protocol")
    return tls_context_from_protocol(protocol)


def bridge_description() -> str:
    return (
        "live TLS 1.3 exporter from the pinned aioquic 1.3.0 key schedule; "
        "version-gated private bridge at the post-Server-Finished 1-RTT stage"
    )
