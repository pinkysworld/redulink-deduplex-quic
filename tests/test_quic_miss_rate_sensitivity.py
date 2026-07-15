"""Validation for the committed native QUIC repair-byte sweep."""
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
        miss_fractions = [float(r["miss_fraction"]) for r in rows]
        self.assertEqual(miss_fractions, sorted(miss_fractions))
        protocol_bytes = [int(r["protocol_stream_bytes"]) for r in rows]
        self.assertEqual(protocol_bytes, sorted(protocol_bytes))
        for row in rows:
            self.assertEqual(row["reconstruction_ok"], "True")
            self.assertGreater(float(row["protocol_stream_multiplier"]), 0.0)

        data = json.loads(json_path.read_text())
        self.assertEqual(data["experiment"], "native_quic_miss_byte_sensitivity")
        self.assertIn("no latency", data["claim_scope"])
        self.assertEqual(len(data["rows"]), len(rows))


if __name__ == "__main__":
    unittest.main()
