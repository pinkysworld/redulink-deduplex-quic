import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "redulink_proto_v0_5.py"


class CliReproducibilityTests(unittest.TestCase):
    def test_random_cli_seed_is_reproducible(self):
        cmd = [
            sys.executable,
            str(SCRIPT),
            "random",
            "--size-mib",
            "1",
            "--chunker",
            "fixed",
            "--seed",
            "123",
        ]
        first = subprocess.check_output(cmd, text=True)
        second = subprocess.check_output(cmd, text=True)
        self.assertEqual(first, second)

    def test_mixed_synthetic_cli_seed_is_reproducible(self):
        cmd = [
            sys.executable,
            str(SCRIPT),
            "synthetic",
            "--variant",
            "mixed",
            "--chunker",
            "cdc",
            "--seed",
            "123",
        ]
        first = subprocess.check_output(cmd, text=True)
        second = subprocess.check_output(cmd, text=True)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
