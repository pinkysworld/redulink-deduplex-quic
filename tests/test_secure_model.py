import unittest
from dataclasses import replace

from src import redulink_secure as secure


def sample_pair():
    warm = (b"A" * 1024) + (b"B" * 1024) + (b"C" * 1024)
    data = (b"A" * 1024) + (b"D" * 1024) + (b"C" * 1024)
    return warm, data


class SecureModelTests(unittest.TestCase):
    def test_authenticated_reconstruction(self):
        warm, data = sample_pair()
        stats = secure.run_bytes(data, warm_dictionary=warm, chunk_size=1024)
        self.assertTrue(stats.reconstruction_ok)
        self.assertGreater(stats.ref_frames, 0)

    def test_tampered_payload_fails_closed(self):
        warm, data = sample_pair()
        frames, _ = secure.encode(data, warm_dictionary=warm, chunk_size=1024)
        idx = next(i for i, f in enumerate(frames) if f.kind == "FULL")
        frames[idx] = replace(frames[idx], payload=b"X" + frames[idx].payload[1:])
        with self.assertRaisesRegex(ValueError, "authentication|chunk id"):
            secure.decode(frames, warm_dictionary=warm, chunk_size=1024)

    def test_tampered_tag_fails_closed(self):
        warm, data = sample_pair()
        frames, _ = secure.encode(data, warm_dictionary=warm, chunk_size=1024)
        frames[0] = replace(frames[0], tag="00" * secure.TAG_BYTES)
        with self.assertRaisesRegex(ValueError, "authentication"):
            secure.decode(frames, warm_dictionary=warm, chunk_size=1024)

    def test_replayed_reference_nonce_fails_closed(self):
        warm, data = sample_pair()
        frames, _ = secure.encode(data, warm_dictionary=warm, chunk_size=1024)
        # Replay the first frame in the same offset position is rejected by nonce
        # only if the expected offset is kept aligned; use zero-length replay test by
        # duplicating the exact first frame and resetting expected offset is not allowed.
        replayed = [frames[0], frames[0]]
        with self.assertRaises(ValueError):
            secure.decode(replayed, warm_dictionary=warm, chunk_size=1024)

    def test_cross_epoch_replay_fails_closed(self):
        warm, data = sample_pair()
        frames, _ = secure.encode(data, warm_dictionary=warm, chunk_size=1024, epoch=1)
        with self.assertRaisesRegex(ValueError, "epoch"):
            secure.decode(frames, warm_dictionary=warm, chunk_size=1024, epoch=2)


if __name__ == "__main__":
    unittest.main()
