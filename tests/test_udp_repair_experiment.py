#!/usr/bin/env python3

import unittest

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototypes"))

import redulink_udp_repair_experiment as udp_demo


class UdpRepairExperimentTests(unittest.TestCase):
    def test_localhost_udp_repair_with_deterministic_loss(self):
        warm, data = udp_demo.demo_payload()
        result = udp_demo.run_udp_repair_experiment(
            warm=warm,
            data=data,
            chunker="fixed",
            chunk_size=1024,
            missing_fraction=0.25,
            seed=7,
            drop_every_nth_data=7,
            timeout=0.05,
            max_retries=6,
        )
        self.assertTrue(result["reconstruction_ok"])
        self.assertGreater(result["semantic_misses"], 0)
        self.assertGreater(result["client_retransmissions"], 0)
        self.assertEqual(result["server_reconstructed_bytes"], result["input_bytes"])
        self.assertGreater(result["model_effective_multiplier_after_repair"], 1.0)


if __name__ == "__main__":
    unittest.main()
