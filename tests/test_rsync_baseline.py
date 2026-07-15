import csv
import tempfile
import unittest
from pathlib import Path

from benchmarks.run_rsync_baseline_manifest import exact_tree_manifest

ROOT = Path(__file__).resolve().parents[1]


class RsyncBaselineTests(unittest.TestCase):
    def test_recorded_rsync_baseline_reports_bytes(self):
        """Validate the packaged real-rsync baseline without launching rsync.

        The benchmark runner is included for reproduction, but invoking rsync
        inside every unit-test discovery run can be environment-sensitive on
        sandboxed CI systems. Artifact review still gets a deterministic check
        that the packaged rsync result exists, reconstructs, and reports useful
        control-plus-data bytes.
        """
        path = ROOT / "results" / "rsync_baseline_external_public.csv"
        self.assertTrue(path.exists())
        with path.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row["reconstruction_ok"], "True")
            self.assertEqual(row["all_rounds_reconstruction_ok"], "True")
            self.assertGreaterEqual(int(row["rsync_rounds"]), 5)
            per_round = [int(value) for value in row["rsync_control_plus_data_bytes_per_round"].split(";")]
            self.assertEqual(len(per_round), int(row["rsync_rounds"]))
            self.assertEqual(int(row["rsync_control_plus_data_bytes"]), sorted(per_round)[len(per_round) // 2])
            self.assertEqual(row["expected_manifest_sha256"], row["reconstructed_manifest_sha256"])
            self.assertEqual(row["expected_manifest_entries"], row["reconstructed_manifest_entries"])
            self.assertGreater(int(row["rsync_control_plus_data_bytes"]), 0)
            self.assertGreater(float(row["rsync_effective_multiplier_control_plus_data"]), 1.0)
            self.assertTrue(row["rsync_executable"])
            self.assertTrue(row["rsync_version"])

    def test_exact_manifest_detects_equal_length_content_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            left = Path(tmp) / "left"
            right = Path(tmp) / "right"
            left.mkdir()
            right.mkdir()
            (left / "artifact.bin").write_bytes(b"AAAA")
            (right / "artifact.bin").write_bytes(b"BBBB")
            left_hash, left_entries = exact_tree_manifest(left)
            right_hash, right_entries = exact_tree_manifest(right)
            self.assertEqual(left_entries, right_entries)
            self.assertNotEqual(left_hash, right_hash)


if __name__ == "__main__":
    unittest.main()
