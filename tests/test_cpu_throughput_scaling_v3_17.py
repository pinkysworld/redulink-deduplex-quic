import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))


@unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
class CpuThroughputScalingTests(unittest.TestCase):
    def test_small_live_sweep_is_paired_and_exact(self):
        from run_cpu_throughput_scaling_v3_17 import run_experiment

        result = asyncio.run(run_experiment(
            blocks=[16, 32],
            rounds=2,
            warmups=0,
            congestion_control_algorithm="reno",
        ))
        self.assertEqual(len(result["rows"]), 8)
        self.assertEqual(len(result["summary"]), 2)
        for summary in result["summary"]:
            self.assertEqual(summary["paired_rounds"], 2)
            self.assertTrue(summary["all_reconstructed"])
            self.assertGreater(summary["process_cpu_ratio_ci95_high"], 0)
            self.assertGreater(summary["process_cpu_ratio_median"], 0)
            self.assertGreater(summary["process_cpu_ratio_median_ci95_high"], 0)
            self.assertGreater(summary["reconstructed_throughput_ratio_ci95_high"], 0)
        for row in result["rows"]:
            self.assertTrue(row["reconstruction_ok"])
            self.assertGreater(row["combined_endpoint_process_cpu_ms"], 0)
            self.assertGreater(row["reconstructed_throughput_mib_s"], 0)


if __name__ == "__main__":
    unittest.main()
