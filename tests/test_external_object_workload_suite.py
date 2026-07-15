from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPORA = ROOT / "data" / "external_public_corpora"


class ExternalObjectWorkloadSuiteTests(unittest.TestCase):
    def test_exact_named_object_roundtrip_and_header_authentication(self) -> None:
        module_path = ROOT / "benchmarks" / "run_external_object_workload_suite.py"
        spec = importlib.util.spec_from_file_location("object_suite", module_path)
        assert spec and spec.loader
        suite = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = suite
        spec.loader.exec_module(suite)
        with tempfile.TemporaryDirectory() as td:
            old = Path(td) / "old"
            new = Path(td) / "new"
            old.mkdir(); new.mkdir()
            (old / "same.bin").write_bytes(b"A" * 4096)
            (new / "same.bin").write_bytes(b"A" * 4096)
            (new / "empty.txt").write_bytes(b"")
            (new / "new.bin").write_bytes(b"B" * 5000)
            plain = suite.object_aligned_redulink(old, new, secure_mode=False)
            secured = suite.object_aligned_redulink(old, new, secure_mode=True)
            self.assertTrue(plain["reconstruction_ok"])
            self.assertTrue(secured["reconstruction_ok"])
            self.assertTrue(secured["wire_serialization_ok"])
            self.assertEqual(plain["object_count"], 3)
            self.assertGreater(secured["object_header_bytes"], plain["object_header_bytes"])
            for name in ("same.bin", "empty.txt", "new.bin"):
                self.assertLessEqual(suite._object_context_id(name), (1 << 62) - 1)

            cas = suite.whole_object_cas(old, new)
            self.assertTrue(cas["reconstruction_ok"])
            self.assertEqual(cas["ref_objects"], 1)
            self.assertEqual(cas["full_objects"], 2)

            chunk_tokens = suite.object_aligned_chunk_token_reuse(old, new)
            self.assertTrue(chunk_tokens["reconstruction_ok"])
            self.assertEqual(chunk_tokens["ref_frames"], 1)

            header = bytearray(suite._encode_object_header("same.bin", 4096, 0, secure_mode=True))
            header[-1] ^= 1
            tampered = suite.ObjectRecord("same.bin", 4096, tuple(), bytes(header))
            with self.assertRaisesRegex(ValueError, "object header authentication"):
                suite._decode_object_records([tampered], warm_root=old, secure_mode=True)

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
            self.assertEqual(row["secure_wire_serialization_ok"], "True")
            self.assertEqual(row["secure_object_header_serialization_ok"], "True")
            self.assertIn("deterministic artifact test key", row["secure_authentication_key_provenance"])
            self.assertEqual(row["chunk_token_reuse_reconstruction_ok"], "True")
            self.assertEqual(row["whole_object_cas_reconstruction_ok"], "True")
            self.assertEqual(row["gzip_reconstruction_ok"], "True")
            self.assertIn("level=6", row["gzip_parameters"])
            self.assertEqual(row["dictionary_budget_chunks"], "8192")
            self.assertGreater(float(row["redulink_multiplier"]), 1.0)
            self.assertNotEqual(row["rsync_total_multiplier"], "")
            # committed evidence must be machine-independent
            self.assertFalse(Path(row["old_tar"]).is_absolute(), "old_tar must be repo-relative")


if __name__ == "__main__":
    unittest.main()
