import random
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_proto_v0_5 as redulink


class MissRateAndAccountingTests(unittest.TestCase):
    def test_miss_rate_falls_back_to_full_and_preserves_reconstruction(self):
        warm = (b"stable-release-page-" * 8192)
        update = warm + (b"new-trailer-field\n" * 256)

        random.seed(7)
        no_miss = redulink.run_bytes(
            update,
            chunker="fixed",
            chunk_size=2048,
            warm=warm,
            miss_rate=0.0,
        )
        random.seed(7)
        some_miss = redulink.run_bytes(
            update,
            chunker="fixed",
            chunk_size=2048,
            warm=warm,
            miss_rate=0.25,
        )

        self.assertTrue(no_miss.reconstruction_ok)
        self.assertTrue(some_miss.reconstruction_ok)
        self.assertGreater(some_miss.full_frames, no_miss.full_frames)
        self.assertGreater(some_miss.wire_bytes, no_miss.wire_bytes)

    def test_wire_byte_accounting_matches_frame_model(self):
        warm = b"dictionary-page-" * 4096
        update = warm + b"small suffix"

        frames, stats = redulink.encode(
            update,
            chunker="fixed",
            chunk_size=1024,
            warm_dictionary=warm,
        )
        expected_wire = sum(
            redulink.FULL_OVERHEAD + len(fr.payload)
            if fr.kind == "FULL"
            else redulink.REF_OVERHEAD
            for fr in frames
        )

        self.assertEqual(stats.wire_bytes, expected_wire)
        self.assertLess(stats.wire_bytes, stats.input_bytes)
        self.assertGreater(stats.effective_multiplier, 1.0)


if __name__ == "__main__":
    unittest.main()
