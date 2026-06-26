import unittest
from dataclasses import replace

from src import redulink_secure as secure


def pair():
    warm = b"A" * 1024 + b"B" * 1024 + b"C" * 1024
    data = b"A" * 1024 + b"D" * 1024 + b"C" * 1024
    return warm, data


class SecureBindingHardeningTests(unittest.TestCase):
    def frames(self):
        warm, data = pair()
        frames, _ = secure.encode(data, warm_dictionary=warm, chunk_size=1024, scope="scope-a", stream_id=3, epoch=5)
        return warm, frames

    def test_wrong_scope_rejected(self):
        warm, frames = self.frames()
        with self.assertRaisesRegex(ValueError, "scope"):
            secure.decode(frames, warm_dictionary=warm, chunk_size=1024, scope="scope-b", stream_id=3, epoch=5)

    def test_wrong_stream_id_rejected(self):
        warm, frames = self.frames()
        with self.assertRaisesRegex(ValueError, "stream"):
            secure.decode(frames, warm_dictionary=warm, chunk_size=1024, scope="scope-a", stream_id=4, epoch=5)

    def test_wrong_offset_rejected(self):
        warm, frames = self.frames()
        frames[1] = replace(frames[1], offset=999)
        with self.assertRaisesRegex(ValueError, "offset|authentication"):
            secure.decode(frames, warm_dictionary=warm, chunk_size=1024, scope="scope-a", stream_id=3, epoch=5)

    def test_wrong_length_rejected(self):
        warm, frames = self.frames()
        frames[0] = replace(frames[0], length=frames[0].length + 1)
        with self.assertRaisesRegex(ValueError, "authentication|length"):
            secure.decode(frames, warm_dictionary=warm, chunk_size=1024, scope="scope-a", stream_id=3, epoch=5)

    def test_wrong_secret_rejected(self):
        warm, frames = self.frames()
        with self.assertRaisesRegex(ValueError, "authentication"):
            secure.decode(frames, warm_dictionary=warm, chunk_size=1024, scope="scope-a", stream_id=3, epoch=5, secret=b"wrong")


if __name__ == "__main__":
    unittest.main()
