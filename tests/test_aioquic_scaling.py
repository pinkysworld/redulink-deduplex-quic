import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AioquicScalingEvidenceTests(unittest.TestCase):
    def test_committed_capacity_sweep_is_exact(self):
        with (ROOT / "results" / "aioquic_scaling_experiment.csv").open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(row["reconstruction_ok"], "True")
            self.assertEqual(row["loss_every"], "0")
            self.assertGreater(int(row["stream_payload_bytes"]), 0)
            self.assertGreater(float(row["stream_payload_multiplier"]), 0.0)
        sixteen = [row for row in rows if int(row["input_bytes"]) == 16 * 1024 * 1024]
        self.assertEqual(len(sixteen), 2)
        self.assertEqual({int(row["receiver_dictionary_thinning_every"]) for row in rows}, {0})
        for row in rows:
            self.assertEqual(row["sender_dictionary_budget_chunks"], row["receiver_dictionary_budget_chunks"])
            self.assertEqual(row["endpoint_dictionary_budget_chunks"], row["sender_dictionary_budget_chunks"])
        by_budget = {int(row["endpoint_dictionary_budget_chunks"]): row for row in sixteen}
        self.assertLess(float(by_budget[8192]["stream_payload_multiplier"]), 1.0)
        self.assertGreater(float(by_budget[24576]["stream_payload_multiplier"]), 1.0)
        self.assertEqual(int(by_budget[8192]["semantic_misses"]), 0)
        self.assertEqual(int(by_budget[24576]["semantic_misses"]), 0)
        self.assertEqual(int(by_budget[8192]["initial_ref_frames"]), 0)
        self.assertGreater(int(by_budget[8192]["initial_full_frames"]), 0)
        self.assertGreater(int(by_budget[24576]["initial_ref_frames"]), 0)
        self.assertGreater(
            int(by_budget[24576]["initial_ref_frames"]),
            int(by_budget[24576]["initial_full_frames"]),
        )


if __name__ == "__main__":
    unittest.main()
