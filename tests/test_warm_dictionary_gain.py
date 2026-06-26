import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_model as redulink


class WarmDictionaryGainTests(unittest.TestCase):
    def test_warm_dictionary_improves_repeated_data(self):
        warm = b"".join(
            f"INFO tenant={i % 64} status=200 template=update object=base\n".encode()
            for i in range(20000)
        )
        update = warm[: len(warm) // 2] + b"new release trailer\n" * 1000

        cold = redulink.run_bytes(update, chunker="cdc", chunk_size=4096)
        warm_stats = redulink.run_bytes(
            update,
            chunker="cdc",
            chunk_size=4096,
            warm=warm,
        )

        self.assertTrue(cold.reconstruction_ok)
        self.assertTrue(warm_stats.reconstruction_ok)
        self.assertGreater(warm_stats.ref_frames, 0)
        self.assertLess(warm_stats.wire_bytes, cold.wire_bytes)
        self.assertGreater(warm_stats.effective_multiplier, cold.effective_multiplier)


if __name__ == "__main__":
    unittest.main()
