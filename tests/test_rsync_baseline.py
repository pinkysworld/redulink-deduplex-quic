import csv
import unittest
from pathlib import Path

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
            self.assertGreater(int(row["rsync_control_plus_data_bytes"]), 0)
            self.assertGreater(float(row["rsync_effective_multiplier_control_plus_data"]), 1.0)


if __name__ == "__main__":
    unittest.main()
