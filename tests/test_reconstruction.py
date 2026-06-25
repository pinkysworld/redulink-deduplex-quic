import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_proto_v0_5 as redulink


class ReconstructionTests(unittest.TestCase):
    def test_full_and_ref_reconstruction_is_byte_exact(self):
        warm = (b"alpha-beta-gamma-" * 1024) + (b"shared-block-" * 1024)
        data = (b"shared-block-" * 1024) + (b"delta-epsilon-" * 1024)

        frames, _ = redulink.encode(
            data,
            chunker="fixed",
            chunk_size=1024,
            warm_dictionary=warm,
        )
        reconstructed = redulink.decode(
            frames,
            chunker="fixed",
            chunk_size=1024,
            warm_dictionary=warm,
        )

        self.assertEqual(reconstructed, data)
        self.assertGreater(sum(1 for fr in frames if fr.kind == "FULL"), 0)
        self.assertGreater(sum(1 for fr in frames if fr.kind == "REF"), 0)

    def test_fixed_and_cdc_chunkers_round_trip(self):
        payload = (b"tenant=17 status=200 path=/api/login\n" * 5000) + b"tail"

        for chunker in ("fixed", "cdc"):
            with self.subTest(chunker=chunker):
                stats = redulink.run_bytes(payload, chunker=chunker, chunk_size=2048)
                self.assertTrue(stats.reconstruction_ok)
                self.assertEqual(stats.input_bytes, len(payload))


if __name__ == "__main__":
    unittest.main()
