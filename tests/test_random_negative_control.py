import random
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_proto_v0_5 as redulink


class RandomNegativeControlTests(unittest.TestCase):
    def test_random_data_does_not_report_false_gain(self):
        rng = random.Random(1337)
        data = bytes(rng.getrandbits(8) for _ in range(512 * 1024))

        for chunker in ("fixed", "cdc"):
            with self.subTest(chunker=chunker):
                stats = redulink.run_bytes(data, chunker=chunker, chunk_size=4096)
                self.assertTrue(stats.reconstruction_ok)
                self.assertEqual(stats.ref_frames, 0)
                self.assertEqual(stats.saving_rate, 0.0)
                self.assertLess(stats.effective_multiplier, 1.0)


if __name__ == "__main__":
    unittest.main()
