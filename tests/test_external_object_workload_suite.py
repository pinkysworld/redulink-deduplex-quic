from __future__ import annotations

import csv
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ExternalObjectWorkloadSuiteTests(unittest.TestCase):
    def test_external_object_suite_runs_and_has_positive_public_cases(self) -> None:
        subprocess.run([sys.executable, str(ROOT / 'benchmarks' / 'run_external_object_workload_suite.py')], cwd=ROOT, check=True)
        out = ROOT / 'results' / 'external_object_workload_suite.csv'
        self.assertTrue(out.exists())
        
        with out.open(newline='') as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row['redulink_reconstruction_ok'], 'True')
            self.assertEqual(row['secure_reconstruction_ok'], 'True')
            self.assertGreater(float(row['redulink_multiplier']), 1.0)
            self.assertNotEqual(row['rsync_total_multiplier'], '')

if __name__ == '__main__':
    unittest.main()
