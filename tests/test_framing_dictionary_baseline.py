"""CI-safe validation of the committed framing-repricing / zstd-patch baseline."""
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
        self.assertGreater(meta["measured_frame_overhead_bytes"]["ref"],
                           meta["model_overhead_bytes"]["ref"],
                           "measured wire framing must exceed the model framing")
        for r in rows:
            model = float(r["model_multiplier"]); repriced = float(r["repriced_multiplier"])
            self.assertGreater(repriced, 0.0)
            self.assertLessEqual(repriced, model,
                                 f"{r['label']}: repricing can only lower the multiplier")
            self.assertGreater(float(r["zstd_patch_multiplier"]), 0.0)
            self.assertEqual(r["reconstruction_ok"], "True")


if __name__ == "__main__":
    unittest.main()
