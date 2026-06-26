import csv
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RsyncBaselineTests(unittest.TestCase):
    @unittest.skipIf(shutil.which("rsync") is None, "rsync is unavailable")
    def test_rsync_manifest_runner_reports_bytes(self):
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            old_dir = tmp / "old"
            new_dir = tmp / "new"
            old_dir.mkdir()
            new_dir.mkdir()
            (old_dir / "payload.txt").write_bytes((b"stable line\n" * 4096) + b"old\n")
            (new_dir / "payload.txt").write_bytes((b"stable line\n" * 4096) + b"new\n")
            manifest = tmp / "manifest.csv"
            output = tmp / "rsync.csv"
            with manifest.open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=["label", "old_path", "new_path"], lineterminator="\n")
                writer.writeheader()
                writer.writerow({"label": "small-public-like-pair", "old_path": str(old_dir), "new_path": str(new_dir)})
            subprocess.run([
                sys.executable,
                str(ROOT / "benchmarks" / "run_rsync_baseline_manifest.py"),
                "--manifest", str(manifest),
                "--output", str(output),
            ], cwd=ROOT, check=True, timeout=30)
            with output.open(newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["reconstruction_ok"], "True")
            self.assertGreater(int(rows[0]["rsync_control_plus_data_bytes"]), 0)
            self.assertGreater(float(rows[0]["rsync_effective_multiplier_control_plus_data"]), 1.0)


if __name__ == "__main__":
    unittest.main()
