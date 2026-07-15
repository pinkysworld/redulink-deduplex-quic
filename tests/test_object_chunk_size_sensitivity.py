import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ObjectChunkSizeSensitivityTests(unittest.TestCase):
    def test_committed_sweep_is_complete_and_exact(self):
        with (ROOT / "results" / "object_chunk_size_sensitivity.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 18)
        self.assertEqual({int(row["chunk_size_bytes"]) for row in rows}, {
            512, 1024, 2048, 4096, 8192, 16384,
        })
        self.assertEqual({row["label"] for row in rows}, {"click", "redis", "nginx"})
        for row in rows:
            self.assertEqual(row["dictionary_budget_bytes"], str(64 * 1024 * 1024))
            self.assertEqual(row["reconstruction_ok"], "True")
            self.assertEqual(row["wire_serialization_ok"], "True")
            self.assertEqual(row["object_header_serialization_ok"], "True")
            self.assertGreater(float(row["multiplier"]), 0.0)

        with (ROOT / "results" / "external_object_workload_suite.csv").open(newline="") as handle:
            object_rows = {
                row["label"].split("-")[0]: row
                for row in csv.DictReader(handle)
            }
        for row in rows:
            if int(row["chunk_size_bytes"]) == 4096:
                self.assertEqual(row["wire_bytes"], object_rows[row["label"]]["secure_wire_bytes"])
                self.assertEqual(row["multiplier"], object_rows[row["label"]]["secure_multiplier"])


if __name__ == "__main__":
    unittest.main()
