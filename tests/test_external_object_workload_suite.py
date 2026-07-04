from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPORA = ROOT / "data" / "external_public_corpora"


class ExternalObjectWorkloadSuiteTests(unittest.TestCase):
    def test_external_object_suite_runs_and_has_positive_public_cases(self) -> None:
        if not CORPORA.exists() or not any(CORPORA.iterdir()):
            self.skipTest(
                "external public corpora are not present; run "
                "`python3 benchmarks/fetch_external_public_corpora.py` first"
            )
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "external_object_workload_suite.csv"
            subprocess.run(
                [sys.executable, str(ROOT / "benchmarks" / "run_external_object_workload_suite.py"),
                 "--output", str(out)],
                cwd=ROOT, check=True,
            )
            self.assertTrue(out.exists())
            with out.open(newline="") as fh:
                rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row["redulink_reconstruction_ok"], "True")
            self.assertEqual(row["secure_reconstruction_ok"], "True")
            self.assertGreater(float(row["redulink_multiplier"]), 1.0)
            self.assertNotEqual(row["rsync_total_multiplier"], "")
            # committed evidence must be machine-independent
            self.assertFalse(Path(row["old_tar"]).is_absolute(), "old_tar must be repo-relative")


if __name__ == "__main__":
    unittest.main()
