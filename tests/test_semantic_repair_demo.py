import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototypes"))

import redulink_semantic_repair_demo as repair


class SemanticRepairDemoTests(unittest.TestCase):
    def test_dictionary_mismatch_repairs_with_full(self):
        warm, update = repair.demo_payload()
        result = repair.semantic_repair_run(
            update,
            warm,
            chunker="fixed",
            chunk_size=1024,
            missing_fraction=0.25,
            seed=7,
        )
        self.assertTrue(result["reconstruction_ok"])
        self.assertGreater(result["misses"], 0)
        self.assertEqual(result["misses"], result["repair_full_frames"])
        self.assertGreater(result["effective_multiplier_after_repair"], 1.0)


if __name__ == "__main__":
    unittest.main()
