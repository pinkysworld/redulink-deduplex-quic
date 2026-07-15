import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SubmissionEvidenceCheckerTests(unittest.TestCase):
    def test_committed_results_compare_to_themselves(self):
        subprocess.run([
            sys.executable,
            str(ROOT / "scripts" / "check_submission_evidence.py"),
            "--generated-dir",
            str(ROOT / "results"),
        ], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
