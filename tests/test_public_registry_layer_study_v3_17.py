import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

import run_public_registry_layer_study_v3_17 as registry_study  # type: ignore


class PublicRegistryLayerStudyTests(unittest.TestCase):
    def test_changed_blob_analysis_separates_refs_and_full_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            warm = root / "warm"
            update = root / "update"
            warm.write_bytes(b"AAAABBBBCCCC")
            update_bytes = b"AAAAXXXXCCCC"
            update.write_bytes(update_bytes)
            descriptor = {
                "digest": "sha256:" + hashlib.sha256(update_bytes).hexdigest(),
                "size": len(update_bytes),
            }
            result = registry_study.analyze_changed_blobs(
                warm_paths=[warm],
                update_descriptors_and_paths=[(descriptor, update)],
                chunk_size=4,
                full_overhead=6,
                ref_overhead=5,
            )
        self.assertEqual(result["changed_layer_bytes"], 12)
        self.assertEqual(result["matched_chunk_bytes_within_changed_layers"], 8)
        self.assertEqual(result["matched_chunk_byte_fraction_within_changed_layers"], 0.666667)
        self.assertEqual(result["ref_frames"], 2)
        self.assertEqual(result["full_frames"], 1)
        self.assertEqual(result["redulink_wire_bytes_for_changed_layers"], 20)
        self.assertTrue(result["reconstruction_ok"])

    def test_measured_binary_frame_overhead_is_positive_and_symmetric(self):
        full_overhead, ref_bytes = registry_study.measured_frame_overheads(4096)
        self.assertGreater(full_overhead, 0)
        self.assertEqual(full_overhead, ref_bytes)


if __name__ == "__main__":
    unittest.main()
