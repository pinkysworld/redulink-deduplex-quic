import importlib.util
import dataclasses
import hashlib
import unittest


class AioquicNativeExperimentTests(unittest.TestCase):
    @unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
    def test_native_runs_use_fresh_connection_key_context(self):
        from prototypes.redulink_aioquic_experiment import run_experiment

        first = run_experiment(payload_blocks=16, missing_every=7)
        second = run_experiment(payload_blocks=16, missing_every=7)
        self.assertNotEqual(
            first["connection_context_sha256"], second["connection_context_sha256"],
        )
        self.assertIn("fresh per-run", first["redulink_key_derivation"])

    @unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
    def test_native_quic_stream_mapping_reconstructs_and_repairs(self):
        from prototypes.redulink_aioquic_experiment import run_experiment

        stats = run_experiment(chunk_size=1024, missing_every=7, wire_format="binary")
        self.assertTrue(stats["reconstruction_ok"])
        self.assertEqual(stats["transport"], "aioquic QUIC bidirectional stream over localhost UDP")
        self.assertFalse(stats["custom_extension_frames"])
        self.assertEqual(stats["wire_format"], "binary")
        self.assertGreater(stats["semantic_misses"], 0)
        self.assertEqual(stats["semantic_misses"], stats["client_repair_full_frames_sent"])
        self.assertEqual(stats["auth_failures"], 0)
        self.assertTrue(stats["tls_server_certificate_verified"])
        self.assertFalse(stats["tls_client_certificate_used"])
        self.assertEqual(len(stats["connection_context_sha256"]), 64)
        self.assertGreater(stats["quic_stream_payload_multiplier_after_repair"], 3.0)
        self.assertEqual(stats["server_reconstructed_bytes"], stats["input_bytes"])

    @unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
    def test_receiver_rejects_authentic_wrong_offset_and_corrupt_ref_state(self):
        from prototypes import redulink_aioquic_experiment as native
        from src import redulink_secure as secure

        secret = b"native-state-test-secret"
        warm, data = native.demo_payload(16)
        frames, _ = secure.encode(
            data, warm_dictionary=warm, secret=secret, epoch=7,
            scope="artifact-aioquic", stream_id=0, chunk_size=1024,
        )
        server = native.QuicReduLinkServer(
            warm=warm, expected_sha256=hashlib.sha256(data).hexdigest(),
            secret=secret, epoch=7, scope="artifact-aioquic", stream_id=0,
            chunker="fixed", chunk_size=1024, missing_every=0,
        )
        server.accept_hello({
            "version": 1, "chunk_size": 1024, "frame_count": len(frames),
            "input_sha256": hashlib.sha256(data).hexdigest(),
        })
        original = frames[0]
        wrong_offset = dataclasses.replace(original, offset=1)
        wrong_offset = dataclasses.replace(
            wrong_offset,
            tag=secure.frame_tag(
                secret=secret, kind=wrong_offset.kind, epoch=wrong_offset.epoch,
                scope=wrong_offset.scope, stream_id=wrong_offset.stream_id,
                offset=wrong_offset.offset, cid=wrong_offset.cid,
                length=wrong_offset.length, nonce=wrong_offset.nonce,
                payload=wrong_offset.payload,
            ),
        )
        with self.assertRaisesRegex(ValueError, "stream offset mismatch"):
            server.accept_frame(seq=0, frame=wrong_offset, repair=False)

        if original.kind == "REF":
            server.dictionary[original.cid] = b"X" * original.length
            with self.assertRaisesRegex(ValueError, "dictionary chunk id mismatch"):
                server.accept_frame(seq=0, frame=original, repair=False)

    @unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
    def test_native_quic_binary_stream_mapping_survives_udp_loss(self):
        from prototypes.redulink_aioquic_experiment import run_experiment

        stats = run_experiment(chunk_size=1024, missing_every=7, wire_format="binary", loss_every=9)
        self.assertTrue(stats["reconstruction_ok"])
        self.assertTrue(stats["datagram_loss_proxy_enabled"])
        self.assertGreater(stats["proxy_client_to_server_datagrams_dropped"] + stats["proxy_server_to_client_datagrams_dropped"], 0)
        self.assertEqual(stats["server_reconstructed_bytes"], stats["input_bytes"])


if __name__ == "__main__":
    unittest.main()
