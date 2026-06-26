import unittest

from src import redulink_secure as secure
from src import redulink_wire as wire


class BinaryWireEncodingTests(unittest.TestCase):
    def test_binary_frame_roundtrip(self):
        frame = secure.SecureFrame(
            kind="FULL",
            epoch=3,
            scope="test-scope",
            stream_id=9,
            offset=1024,
            cid="00" * 16,
            length=5,
            nonce=44,
            tag="11" * 16,
            payload=b"hello",
        )
        encoded = wire.encode_message({"t": "FRAME", "seq": 7, "repair": True, "frame": frame})
        decoded, size = wire.decode_payload(encoded[4:]), len(encoded)
        self.assertEqual(decoded.t, "FRAME")
        self.assertEqual(decoded.obj["seq"], 7)
        self.assertTrue(decoded.obj["repair"])
        self.assertEqual(decoded.obj["frame"], frame)
        self.assertEqual(size, len(encoded))

    def test_missing_roundtrip(self):
        msg = {"t": "MISSING", "items": [{"seq": 2, "cid": "ab" * 16, "length": 1024}]}
        body = wire.encode_message(msg)[4:]
        decoded = wire.decode_payload(body)
        self.assertEqual(decoded.obj, msg)


if __name__ == "__main__":
    unittest.main()
