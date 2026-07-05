"""Validation for the committed QUIC miss-rate sensitivity sweep."""
import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestQuicMissRateSensitivity(unittest.TestCase):
    def test_committed_sensitivity_files_are_consistent(self):
        csv_path = ROOT / "results" / "quic_miss_rate_sensitivity.csv"
        json_path = ROOT / "results" / "quic_miss_rate_sensitivity.json"
        self.assertTrue(csv_path.exists())
        self.assertTrue(json_path.exists())

        with csv_path.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 4)
        miss_fractions = [float(r["miss_fraction_mean"]) for r in rows]
        self.assertEqual(miss_fractions, sorted(miss_fractions))
        for row in rows:
            self.assertEqual(row["all_reconstructed"], "True")
            self.assertGreater(float(row["redulink_stream_multiplier_mean"]), 0.0)
            self.assertGreater(float(row["rl_over_raw_completion_mean"]), 0.0)

        data = json.loads(json_path.read_text())
        self.assertEqual(data["experiment"], "measured_quic_miss_rate_sensitivity")
        self.assertIn("not kernel tc/netem", data["note"])
        self.assertEqual(len(data["summary"]), len(rows))


if __name__ == "__main__":
    unittest.main()
