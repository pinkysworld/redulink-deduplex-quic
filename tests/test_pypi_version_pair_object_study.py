"""CI-safe validation of the committed independent PyPI version-pair object study.

Does not re-download anything; it checks the committed result file is well-formed,
hash-pinned, and reports byte-exact reconstruction for every real package pair.
"""
import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "results" / "pypi_version_pair_object_study.csv"


class TestPypiVersionPairObjectStudy(unittest.TestCase):
    def test_study_file_is_wellformed_and_reconstructs(self):
        self.assertTrue(CSV.exists(), "pypi_version_pair_object_study.csv missing")
        with CSV.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 3, "expected several package pairs")
        required = {
            "package", "old_version", "new_version", "old_sha256", "new_sha256",
            "unchanged_file_count", "new_file_count", "input_bytes",
            "redulink_multiplier", "secure_multiplier", "reconstruction_ok",
        }
        for r in rows:
            self.assertTrue(required.issubset(r.keys()))
            # hash-pinned: 64-hex sha256 recorded for each real wheel
            self.assertEqual(len(r["old_sha256"]), 64)
            self.assertEqual(len(r["new_sha256"]), 64)
            # byte-exact reconstruction for every real pair
            self.assertEqual(r["reconstruction_ok"], "True", r["package"])
            self.assertGreater(float(r["redulink_multiplier"]), 0.0)
            self.assertLessEqual(
                int(r["unchanged_file_count"]), int(r["new_file_count"])
            )


if __name__ == "__main__":
    unittest.main()
