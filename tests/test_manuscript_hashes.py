import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ManuscriptHashTests(unittest.TestCase):
    def test_bound_manuscript_files_match_manifest(self):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_manuscript_hashes.py")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
