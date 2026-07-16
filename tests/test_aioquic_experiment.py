import importlib.util
import dataclasses
import hashlib
import unittest


class AioquicNativeExperimentTests(unittest.TestCase):
    @unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
    def test_native_runs_use_fresh_connection_key_context(self):
        from prototypes.redulink_aioquic_experiment import run_experiment

        first = run_experiment(
            payload_blocks=16, missing_every=7,
            expose_exporter_debug_hash=True,
        )
        second = run_experiment(
            payload_blocks=16, missing_every=7,
            expose_exporter_debug_hash=True,
        )
        self.assertNotEqual(
            first["connection_context_sha256"], second["connection_context_sha256"],
        )
        self.assertTrue(first["connection_contexts_match"])
        self.assertEqual(first["tls_exporter_label"], "EXPERIMENTAL-ReduLink-v1")
        self.assertEqual(first["tls_exporter_output_bytes"], 32)
        self.assertEqual(len(first["tls_exporter_context_sha256"]), 64)
        self.assertTrue(first["tls_exporter_live"])
        self.assertTrue(first["tls_exporter_outputs_match"])
        self.assertIn("post-Server-Finished", first["tls_exporter_bridge"])
        self.assertIn("live TLS 1.3 exporter", first["redulink_key_derivation"])
        self.assertNotEqual(
            first["tls_exporter_output_sha256"],
            second["tls_exporter_output_sha256"],
        )

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
        self.assertTrue(stats["tls_exporter_live"])
        self.assertTrue(stats["tls_exporter_outputs_match"])
        self.assertEqual(len(stats["connection_context_sha256"]), 64)
        self.assertGreater(stats["quic_stream_payload_multiplier_after_repair"], 3.0)
        self.assertEqual(stats["server_reconstructed_bytes"], stats["input_bytes"])
        self.assertEqual(stats["authenticated_transfer_length"], stats["input_bytes"])
        self.assertEqual(stats["application_stream_id"], 0)
        self.assertEqual(
            stats["quic_stream_payload_total_bytes"],
            stats["protocol_stream_payload_total_bytes_excluding_diagnostics"],
        )
        self.assertEqual(
            stats["protocol_stream_payload_total_bytes_excluding_diagnostics"],
            stats["forward_protocol_stream_bytes"] + stats["reverse_repair_control_stream_bytes"],
        )
        self.assertGreater(stats["diagnostic_stats_stream_bytes"], 0)
        self.assertEqual(stats["client_elapsed_ms"], stats["client_network_elapsed_ms"])
        self.assertGreaterEqual(stats["client_end_to_end_elapsed_ms"],
                                stats["client_network_elapsed_ms"])
        self.assertGreaterEqual(stats["client_preparation_elapsed_ms"], 0.0)

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
            expected_length=len(data),
            secret=secret, epoch=7, scope="artifact-aioquic", stream_id=0,
            chunker="fixed", chunk_size=1024, missing_every=0,
        )
        server.accept_hello({
            "version": 1, "chunk_size": 1024, "frame_count": len(frames),
            "input_length": len(data),
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
    def test_receiver_enforces_authenticated_length_and_quota(self):
        from prototypes import redulink_aioquic_experiment as native

        warm, data = native.demo_payload(16)
        common = dict(
            warm=warm,
            expected_sha256=hashlib.sha256(data).hexdigest(),
            expected_length=len(data),
            secret=b"length-test-secret",
            epoch=7,
            scope="artifact-aioquic",
            stream_id=0,
            chunker="fixed",
            chunk_size=1024,
            missing_every=0,
        )
        with self.assertRaisesRegex(ValueError, "quota"):
            native.QuicReduLinkServer(**common, max_reconstructed_bytes=len(data) - 1)

        server = native.QuicReduLinkServer(**common)
        with self.assertRaisesRegex(ValueError, "input length mismatch"):
            server.accept_hello({
                "version": 1,
                "chunk_size": 1024,
                "frame_count": 16,
                "input_length": len(data) + 1,
                "input_sha256": hashlib.sha256(data).hexdigest(),
            })

    @unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
    def test_native_quic_binary_stream_mapping_survives_udp_loss(self):
        from prototypes.redulink_aioquic_experiment import run_experiment

        stats = run_experiment(chunk_size=1024, missing_every=7, wire_format="binary", loss_every=9)
        self.assertTrue(stats["reconstruction_ok"])
        self.assertTrue(stats["datagram_loss_proxy_enabled"])
        self.assertGreater(stats["proxy_client_to_server_datagrams_dropped"] + stats["proxy_server_to_client_datagrams_dropped"], 0)
        self.assertEqual(stats["server_reconstructed_bytes"], stats["input_bytes"])

    @unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
    def test_zero_dictionary_thinning_has_no_forced_miss(self):
        from prototypes.redulink_aioquic_experiment import run_experiment

        stats = run_experiment(chunk_size=1024, missing_every=0, wire_format="binary")
        self.assertEqual(stats["semantic_misses"], 0)
        self.assertEqual(stats["repair_full_frames"], 0)
        self.assertTrue(stats["reconstruction_ok"])

    @unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
    def test_sender_rejects_malformed_batched_repair_requests(self):
        from prototypes import redulink_aioquic_experiment as native
        from src import redulink_secure as secure

        warm, data = native.demo_payload(16)
        frames, _ = secure.encode(
            data, warm_dictionary=warm, secret=b"repair-list-secret", epoch=7,
            scope="artifact-aioquic", stream_id=0, chunk_size=1024,
        )
        ref_seq = next(i for i, frame in enumerate(frames) if frame.kind == "REF")
        full_seq = next(i for i, frame in enumerate(frames) if frame.kind == "FULL")
        ref = frames[ref_seq]
        valid = {"seq": ref_seq, "cid": ref.cid, "length": ref.length}
        self.assertEqual(native.validate_missing_items([valid], frames), [(ref_seq, ref)])
        cases = [
            ([valid, valid], "duplicate"),
            ([{"seq": len(frames), "cid": ref.cid, "length": ref.length}], "invalid"),
            ([{"seq": full_seq, "cid": frames[full_seq].cid,
               "length": frames[full_seq].length}], "non-REF"),
            ([{**valid, "cid": "00" * 16}], "identifier"),
            ([{**valid, "length": ref.length + 1}], "length"),
        ]
        for items, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(RuntimeError, message):
                    native.validate_missing_items(items, frames)

    @unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
    def test_receiver_enforces_repair_phase_and_completion_digest(self):
        from prototypes import redulink_aioquic_experiment as native
        from src import redulink_secure as secure

        secret = b"repair-phase-secret"
        warm, data = native.demo_payload(16)
        frames, _ = secure.encode(
            data, warm_dictionary=warm, secret=secret, epoch=7,
            scope="artifact-aioquic", stream_id=0, chunk_size=1024,
        )
        server = native.QuicReduLinkServer(
            warm=warm, expected_sha256="00" * 32, expected_length=len(data),
            secret=secret, epoch=7, scope="artifact-aioquic", stream_id=0,
            chunker="fixed", chunk_size=1024, missing_every=1,
        )
        server.accept_hello({
            "version": 1, "chunk_size": 1024, "frame_count": len(frames),
            "input_length": len(data), "input_sha256": "00" * 32,
        })
        ref_seq = next(i for i, frame in enumerate(frames) if frame.kind == "REF")
        for seq in range(ref_seq + 1):
            server.accept_frame(seq=seq, frame=frames[seq], repair=False)
        ref = frames[ref_seq]
        repair = native.make_full_repair(
            ref,
            native.build_secure_dictionary(
                warm, secret=secret, epoch=7, scope="artifact-aioquic",
                chunker="fixed", chunk_size=1024,
            )[ref.cid],
            secret=secret,
            nonce=max(frame.nonce for frame in frames) + 1,
        )
        with self.assertRaisesRegex(ValueError, "before END_ROUND"):
            server.accept_frame(seq=ref_seq, frame=repair, repair=True)

        server.round_ended = True
        wrong = dataclasses.replace(repair, length=repair.length - 1)
        with self.assertRaisesRegex(ValueError, "repair metadata"):
            server.accept_frame(seq=ref_seq, frame=wrong, repair=True)

        # A fully assembled sequence with a server-configured wrong digest must fail closed.
        complete = native.QuicReduLinkServer(
            warm=warm, expected_sha256="00" * 32, expected_length=len(data),
            secret=secret, epoch=7, scope="artifact-aioquic", stream_id=0,
            chunker="fixed", chunk_size=1024, missing_every=0,
        )
        complete.accept_hello({
            "version": 1, "chunk_size": 1024, "frame_count": len(frames),
            "input_length": len(data), "input_sha256": "00" * 32,
        })
        for seq, frame in enumerate(frames):
            complete.accept_frame(seq=seq, frame=frame, repair=False)
        complete.round_ended = True
        with self.assertRaisesRegex(ValueError, "digest"):
            complete.finalize_reconstruction()


if __name__ == "__main__":
    unittest.main()
