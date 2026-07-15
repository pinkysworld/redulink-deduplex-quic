"""CI-safe validation of the framing-repricing / zstd-dictionary baseline."""
import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "results" / "framing_dictionary_baseline.csv"
JSON = ROOT / "results" / "framing_dictionary_baseline.json"


class FramingDictionaryBaselineTests(unittest.TestCase):
    def test_committed_baseline_is_wellformed(self):
        self.assertTrue(CSV.exists() and JSON.exists())
        with CSV.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 4)
        meta = json.loads(JSON.read_text())
        self.assertEqual(meta["wire_overhead_formula"], "85 + UTF-8 scope length")
        self.assertEqual(meta["provenance"]["libzstd_version"], "1.5.7")
        self.assertEqual(meta["provenance"]["zstd_window_log"], 21)
        self.assertEqual(meta["provenance"]["zstd_window_sensitivity_log"], 24)
        self.assertEqual(meta["measured_frame_overhead_bytes"]["ref"], 114)
        self.assertGreater(meta["measured_frame_overhead_bytes"]["ref"],
                           meta["model_overhead_bytes"]["ref"],
                           "measured wire framing must exceed the model framing")
        for r in rows:
            model = float(r["model_multiplier"]); repriced = float(r["repriced_multiplier"])
            self.assertGreater(repriced, 0.0)
            self.assertLessEqual(repriced, model,
                                 f"{r['label']}: repricing can only lower the multiplier")
            self.assertGreater(float(r["zstd_dictionary_multiplier"]), 0.0)
            self.assertEqual(r["libzstd_version"], "1.5.7")
            self.assertEqual(r["zstd_dictionary_reconstruction_ok"], "True")
            self.assertEqual(r["zstd_window_log"], "21")
            self.assertEqual(r["zstd_window_sensitivity_log"], "24")
            self.assertGreater(float(r["zstd_window_sensitivity_multiplier"]), 0.0)
            self.assertEqual(r["zstd_window_sensitivity_reconstruction_ok"], "True")
            self.assertEqual(r["zstd_expected_sha256"], r["zstd_reconstructed_sha256"])
            self.assertEqual(r["gzip_reconstruction_ok"], "True")
            self.assertIn("level=6", r["gzip_parameters"])
            self.assertEqual(r["reconstruction_ok"], "True")


if __name__ == "__main__":
    unittest.main()
