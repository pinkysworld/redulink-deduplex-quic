import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_model as redulink


class FrameValidationTests(unittest.TestCase):
    def test_ref_length_mismatch_fails_closed(self):
        warm = b"shared-payload-" * 512
        frames, _ = redulink.encode(
            warm,
            chunker="fixed",
            chunk_size=1024,
            warm_dictionary=warm,
        )
        ref = next(fr for fr in frames if fr.kind == "REF")
        bad = redulink.Frame(ref.kind, ref.cid, ref.payload, ref.length + 1)

        with self.assertRaisesRegex(ValueError, "REF frame length mismatch"):
            redulink.decode([bad], chunker="fixed", chunk_size=1024, warm_dictionary=warm)

    def test_full_length_mismatch_fails_closed(self):
        payload = b"payload" * 200
        frame = redulink.Frame("FULL", redulink.cid(payload), payload, len(payload) + 1)

        with self.assertRaisesRegex(ValueError, "FULL frame length mismatch"):
            redulink.decode([frame], chunker="fixed", chunk_size=1024)


if __name__ == "__main__":
    unittest.main()
