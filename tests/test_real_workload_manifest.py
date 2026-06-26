import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RealWorkloadManifestTests(unittest.TestCase):
    def test_manifest_runner_accepts_file_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            old = d / "old.bin"
            new = d / "new.bin"
            old.write_bytes((b"A" * 4096) + (b"B" * 4096))
            new.write_bytes((b"A" * 4096) + (b"C" * 4096))
            manifest = d / "manifest.csv"
            out = d / "out.csv"
            with manifest.open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=["label", "old_path", "new_path", "chunker", "chunk_size"])
                writer.writeheader(); writer.writerow({"label": "pair", "old_path": old, "new_path": new, "chunker": "fixed", "chunk_size": "4096"})
            subprocess.run([sys.executable, str(ROOT / "benchmarks" / "run_real_workload_manifest.py"), "--manifest", str(manifest), "--output", str(out)], check=True, cwd=ROOT)
            with out.open() as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["label"], "pair")
            self.assertEqual(rows[0]["redulink_reconstruction_ok"], "True")
            self.assertGreater(float(rows[0]["redulink_multiplier"]), 1.0)


if __name__ == "__main__":
    unittest.main()
