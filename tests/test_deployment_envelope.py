import csv
import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.derive_deployment_envelope import derive

ROOT = Path(__file__).resolve().parents[1]


class DeploymentEnvelopeTests(unittest.TestCase):
    def test_committed_envelope_is_exact_and_capacity_gated(self):
        expected = derive(
            ROOT / "results" / "quic_miss_rate_sensitivity.csv",
            ROOT / "results" / "aioquic_scaling_experiment.csv",
        )
        committed = json.loads(
            (ROOT / "results" / "deployment_envelope.json").read_text(encoding="utf-8")
        )
        self.assertEqual(committed, expected)
        self.assertEqual(committed["exact_byte_equation"], "B(m)=15914+1149m")
        self.assertEqual(committed["max_integer_beneficial_misses"], 71)
        self.assertEqual(committed["first_nonbeneficial_misses"], 72)
        self.assertEqual(committed["capacity_overflow_initial_ref_frames"], 0)
        self.assertGreater(committed["capacity_retained_initial_ref_frames"], 0)
        self.assertLess(committed["capacity_overflow_multiplier"], 1.0)
        self.assertGreater(committed["capacity_retained_multiplier"], 1.0)

    def test_non_linear_input_is_rejected(self):
        miss_source = ROOT / "results" / "quic_miss_rate_sensitivity.csv"
        with miss_source.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        rows[-1]["protocol_stream_bytes"] = str(int(rows[-1]["protocol_stream_bytes"]) + 1)
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / "miss.csv"
            with changed.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "linear model"):
                derive(changed, ROOT / "results" / "aioquic_scaling_experiment.csv")


if __name__ == "__main__":
    unittest.main()
