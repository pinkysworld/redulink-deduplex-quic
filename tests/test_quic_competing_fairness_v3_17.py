import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))


@unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
class QuicCompetingFairnessTests(unittest.TestCase):
    def test_unshaped_smoke_uses_barrier_and_reconstructs_every_flow(self):
        from run_quic_competing_fairness_v3_17 import run_experiment

        result = asyncio.run(run_experiment(
            rounds=1,
            raw_blocks=16,
            redulink_blocks=64,
            congestion_control_algorithm="reno",
            device=None,
        ))
        self.assertEqual(len(result["pairs"]), 3)
        self.assertEqual(len(result["summary"]), 3)
        for pair in result["pairs"]:
            self.assertTrue(pair["all_reconstructed"])
            self.assertGreater(pair["encoded_goodput_jain_fairness"], 0)
            self.assertLessEqual(pair["encoded_goodput_jain_fairness"], 1)
            self.assertEqual(len(pair["flows"]), 2)
            for flow in pair["flows"]:
                self.assertTrue(flow["reconstruction_ok"])
                self.assertEqual(flow["congestion_control_algorithm"], "reno")
                self.assertGreater(flow["client_completion_ms"], 0)
                self.assertLessEqual(flow["client_ttfb_ms"], flow["client_completion_ms"])
                self.assertGreaterEqual(
                    flow["connection_plus_application_completion_ms"],
                    flow["client_completion_ms"],
                )


if __name__ == "__main__":
    unittest.main()
