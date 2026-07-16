"""Cross-check protocol vectors with independent transcript and HKDF code."""
from __future__ import annotations

import hashlib
import hmac
import json
import unittest
from pathlib import Path

from src import redulink_key_schedule as ks
from src import redulink_secure as secure
from src import redulink_tls_exporter as tls_exporter

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads((ROOT / "docs" / "protocol_test_vectors.json").read_text())


def lp(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def independent_hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """Minimal RFC 5869 expansion written independently of production code."""

    output = bytearray()
    previous = b""
    for counter in range(1, 256):
        previous = hmac.new(
            prk, previous + info + bytes((counter,)), hashlib.sha256,
        ).digest()
        output.extend(previous)
        if len(output) >= length:
            return bytes(output[:length])
    raise ValueError("requested HKDF output is too long")


def independent_hkdf_expand_label(
    secret: bytes, label: bytes, context: bytes, length: int,
) -> bytes:
    full_label = b"tls13 " + label
    hkdf_label = (
        length.to_bytes(2, "big")
        + len(full_label).to_bytes(1, "big")
        + full_label
        + len(context).to_bytes(1, "big")
        + context
    )
    return independent_hkdf_expand(secret, hkdf_label, length)


class ProtocolVectorTests(unittest.TestCase):
    def test_record_vector_with_independent_encoder(self):
        v = VECTORS["record_authentication"]
        secret = bytes.fromhex(v["secret_hex"])
        chunk = bytes.fromhex(v["chunk_hex"])
        scope = v["scope_utf8"].encode("utf-8")
        cid_transcript = (
            b"ReduLink CID transcript\x00\x01"
            + int(v["epoch"]).to_bytes(8, "big")
            + lp(scope)
            + hashlib.sha256(chunk).digest()
        )
        cid = hmac.new(secret, cid_transcript, hashlib.sha256).digest()[:16]
        self.assertEqual(cid_transcript.hex(), v["cid_transcript_hex"])
        self.assertEqual(cid.hex(), v["cid_hex"])
        self.assertEqual(
            secure.cid_transcript(chunk, epoch=v["epoch"], scope=v["scope_utf8"]),
            cid_transcript,
        )
        self.assertEqual(
            secure.secure_cid(chunk, secret=secret, epoch=v["epoch"], scope=v["scope_utf8"]),
            cid.hex(),
        )

        f = v["frame"]
        frame_transcript = (
            b"ReduLink frame transcript\x00\x01"
            + b"\x01"
            + int(v["epoch"]).to_bytes(8, "big")
            + lp(scope)
            + int(f["stream_id"]).to_bytes(8, "big")
            + int(f["offset"]).to_bytes(8, "big")
            + cid
            + int(f["length"]).to_bytes(4, "big")
            + int(f["nonce"]).to_bytes(8, "big")
            + hashlib.sha256(chunk).digest()
        )
        tag = hmac.new(secret, frame_transcript, hashlib.sha256).digest()[:16]
        self.assertEqual(frame_transcript.hex(), f["frame_transcript_hex"])
        self.assertEqual(tag.hex(), f["tag_hex"])
        self.assertEqual(
            secure.frame_transcript(
                kind=f["kind"], epoch=v["epoch"], scope=v["scope_utf8"],
                stream_id=f["stream_id"], offset=f["offset"], cid=cid.hex(),
                length=f["length"], nonce=f["nonce"], payload=chunk,
            ),
            frame_transcript,
        )

    def test_key_schedule_vector_with_independent_implementation(self):
        v = VECTORS["record_authentication"]
        k = VECTORS["key_schedule"]
        label = k["tls_exporter_label_ascii"].encode("ascii")
        alpn = k["alpn_utf8"].encode("utf-8")
        scope = v["scope_utf8"].encode("utf-8")
        session_id = bytes.fromhex(k["application_session_id_hex"])
        connection_transcript = (
            b"ReduLink connection context\x00\x01"
            + lp(alpn)
            + lp(session_id)
        )
        connection_context = hashlib.sha256(connection_transcript).digest()
        self.assertEqual(connection_context.hex(), k["connection_context_hex"])

        exporter_transcript = (
            b"ReduLink TLS exporter context\x00\x01"
            + lp(alpn)
            + lp(scope)
            + lp(connection_context)
        )
        exporter_context = hashlib.sha256(exporter_transcript).digest()
        self.assertEqual(exporter_context.hex(), k["tls_exporter_context_hex"])

        key_info = (
            b"ReduLink key context\x00\x01"
            + lp(label)
            + lp(alpn)
            + int(v["epoch"]).to_bytes(8, "big")
            + lp(scope)
            + lp(connection_context)
            + lp(bytes.fromhex(k["stream_context_hex"]))
            + lp(k["direction_utf8"].encode("utf-8"))
        )
        self.assertEqual(key_info.hex(), k["key_info_hex"])

        exporter_master_secret = bytes.fromhex(k["tls_exporter_master_secret_hex"])
        label_secret = independent_hkdf_expand_label(
            exporter_master_secret,
            label,
            hashlib.sha256(b"").digest(),
            32,
        )
        exporter_output = independent_hkdf_expand_label(
            label_secret,
            b"exporter",
            hashlib.sha256(exporter_context).digest(),
            32,
        )
        self.assertEqual(exporter_output.hex(), k["tls_exporter_output_hex"])
        prk = hmac.new(label, exporter_output, hashlib.sha256).digest()
        record_secret = independent_hkdf_expand(prk, key_info, 32)
        self.assertEqual(record_secret.hex(), k["derived_record_secret_hex"])

    def test_production_key_schedule_matches_vector_at_both_endpoints(self):
        v = VECTORS["record_authentication"]
        k = VECTORS["key_schedule"]
        session_id = bytes.fromhex(k["application_session_id_hex"])
        client_context = ks.derive_connection_context(
            alpn=k["alpn_utf8"], application_session_id=session_id,
        )
        server_context = ks.derive_connection_context(
            alpn=k["alpn_utf8"], application_session_id=bytes(session_id),
        )
        self.assertEqual(client_context, server_context)
        self.assertEqual(client_context.hex(), k["connection_context_hex"])
        self.assertEqual(
            ks.tls_exporter_context(
                alpn=k["alpn_utf8"], scope=v["scope_utf8"],
                connection_context=client_context,
            ).hex(),
            k["tls_exporter_context_hex"],
        )
        context = ks.ReduLinkKeyContext(
            alpn=k["alpn_utf8"], epoch=v["epoch"], scope=v["scope_utf8"],
            connection_context=server_context,
            stream_context=bytes.fromhex(k["stream_context_hex"]),
            direction=k["direction_utf8"],
        )
        self.assertEqual(ks.context_info(context).hex(), k["key_info_hex"])
        self.assertEqual(
            tls_exporter.export_keying_material_from_secret(
                exporter_master_secret=bytes.fromhex(
                    k["tls_exporter_master_secret_hex"],
                ),
                label=k["tls_exporter_label_ascii"].encode("ascii"),
                context_value=bytes.fromhex(k["tls_exporter_context_hex"]),
                length=k["tls_exporter_output_bytes"],
            ).hex(),
            k["tls_exporter_output_hex"],
        )
        self.assertEqual(
            ks.derive_redulink_secret(
                bytes.fromhex(k["tls_exporter_output_hex"]), context,
            ).hex(),
            k["derived_record_secret_hex"],
        )


if __name__ == "__main__":
    unittest.main()
