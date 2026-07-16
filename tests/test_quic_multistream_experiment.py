import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))


@unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
class QuicMultistreamExperimentTests(unittest.TestCase):
    def test_live_connection_uses_distinct_streams_and_exact_reconstruction(self):
        from run_quic_multistream_experiment import run_experiment

        result = asyncio.run(run_experiment(
            rounds=1,
            blocker_blocks=128,
            small_blocks=16,
            small_count=2,
            congestion_control_algorithm="reno",
        ))
        self.assertTrue(result["aggregate"]["all_reconstructed"])
        self.assertEqual(result["aggregate"]["rounds"], 1)
        for mode in result["modes"]:
            self.assertTrue(mode["connection_contexts_match"])
            self.assertEqual(mode["actual_stream_ids"], [0, 4, 8])
            for row in mode["rows"]:
                self.assertTrue(row["reconstruction_ok"])
                self.assertTrue(row["tls_exporter_live"])
                self.assertTrue(row["tls_exporter_outputs_match"])
                self.assertEqual(row["measurement_control_stream_bytes_excluded"], 13)
        summary = result["round_summary"][0]
        self.assertEqual(summary["small_stream_count"], 2)
        self.assertGreaterEqual(
            summary["multiplexed_small_streams_finishing_before_blocker"], 1,
        )


if __name__ == "__main__":
    unittest.main()
