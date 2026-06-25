import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_proto_v0_5 as redulink


class RefMissFailureTests(unittest.TestCase):
    def test_ref_fails_safely_when_receiver_lacks_dictionary(self):
        warm = b"known-chunk-" * 4096
        data = b"known-chunk-" * 4096

        frames, _ = redulink.encode(
            data,
            chunker="fixed",
            chunk_size=1024,
            warm_dictionary=warm,
        )

        self.assertTrue(any(fr.kind == "REF" for fr in frames))
        with self.assertRaisesRegex(ValueError, "REF miss"):
            redulink.decode(frames, chunker="fixed", chunk_size=1024, warm_dictionary=b"")


if __name__ == "__main__":
    unittest.main()
