import importlib.util
import unittest


class AioquicNativeExperimentTests(unittest.TestCase):
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
        self.assertGreater(stats["quic_stream_payload_multiplier_after_repair"], 3.0)
        self.assertEqual(stats["server_reconstructed_bytes"], stats["input_bytes"])

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
