import unittest
import asyncio
from unittest import mock

from src import redulink_secure as secure
from src import redulink_wire as wire


class BinaryWireEncodingTests(unittest.TestCase):
    def test_hello_roundtrip_includes_authenticated_input_length(self):
        msg = {
            "t": "HELLO",
            "version": 1,
            "chunk_size": 8192,
            "frame_count": 17,
            "input_length": 131072,
            "input_sha256": "ab" * 32,
        }
        decoded = wire.decode_payload(wire.encode_message(msg)[4:])
        self.assertEqual(decoded.obj, msg)

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

    def test_quic_stream_id_uses_full_62_bit_space(self):
        frame = secure.SecureFrame(
            kind="REF",
            epoch=3,
            scope="test-scope",
            stream_id=(1 << 40) + 3,
            offset=0,
            cid="00" * 16,
            length=5,
            nonce=44,
            tag="11" * 16,
        )
        encoded = wire.encode_message({"t": "FRAME", "seq": 7, "frame": frame})
        decoded = wire.decode_payload(encoded[4:])
        self.assertEqual(decoded.obj["frame"].stream_id, (1 << 40) + 3)

    def test_rejects_stream_ids_outside_quic_range(self):
        base = secure.SecureFrame(
            kind="REF", epoch=1, scope="s", stream_id=0, offset=0,
            cid="00" * 16, length=1, nonce=1, tag="11" * 16,
        )
        for invalid in (-1, 1 << 62):
            frame = secure.SecureFrame(**{**base.__dict__, "stream_id": invalid})
            with self.subTest(stream_id=invalid):
                with self.assertRaisesRegex(ValueError, "stream_id"):
                    wire.encode_message({"t": "FRAME", "seq": 0, "frame": frame})

    def test_rejects_stream_offsets_outside_quic_range(self):
        base = secure.SecureFrame(
            kind="REF", epoch=1, scope="s", stream_id=0, offset=0,
            cid="00" * 16, length=1, nonce=1, tag="11" * 16,
        )
        for invalid in (-1, 1 << 62):
            frame = secure.SecureFrame(**{**base.__dict__, "offset": invalid})
            with self.subTest(offset=invalid):
                with self.assertRaisesRegex(ValueError, "offset"):
                    wire.encode_message({"t": "FRAME", "seq": 0, "frame": frame})

    def test_missing_roundtrip(self):
        msg = {"t": "MISSING", "items": [{"seq": 2, "cid": "ab" * 16, "length": 1024}]}
        body = wire.encode_message(msg)[4:]
        decoded = wire.decode_payload(body)
        self.assertEqual(decoded.obj, msg)

    def test_first_byte_measurement_roundtrip(self):
        msg = {"t": "FIRST_BYTE", "offset": 0}
        body = wire.encode_message(msg)[4:]
        self.assertEqual(wire.decode_payload(body).obj, msg)

    def test_missing_encoder_enforces_single_message_item_bound(self):
        items = [
            {"seq": 0, "cid": "ab" * 16, "length": 1024},
            {"seq": 1, "cid": "cd" * 16, "length": 1024},
        ]
        with mock.patch.object(wire, "MAX_MISSING_ITEMS", 1):
            with self.assertRaisesRegex(ValueError, "item count"):
                wire.encode_message({"t": "MISSING", "items": items})

    def test_rejects_truncated_and_trailing_frame_data(self):
        frame = secure.SecureFrame(
            kind="REF", epoch=1, scope="s", stream_id=0, offset=0,
            cid="00" * 16, length=10, nonce=1, tag="11" * 16,
        )
        body = wire.encode_message({"t": "FRAME", "seq": 0, "frame": frame})[4:]
        with self.assertRaisesRegex(ValueError, "truncated"):
            wire.decode_payload(body[:-1])
        with self.assertRaisesRegex(ValueError, "trailing"):
            wire.decode_payload(body + b"x")

    def test_rejects_trailing_control_data_and_invalid_missing_length(self):
        with self.assertRaisesRegex(ValueError, "END_ROUND"):
            wire.decode_payload(bytes([wire.END_ROUND]) + b"x")
        body = wire.encode_message({"t": "MISSING", "items": []})[4:]
        with self.assertRaisesRegex(ValueError, "MISSING length"):
            wire.decode_payload(body + b"x")

    def test_reader_rejects_unbounded_length_before_body_read(self):
        async def check():
            reader = asyncio.StreamReader()
            reader.feed_data((wire.MAX_MESSAGE_BYTES + 1).to_bytes(4, "big"))
            reader.feed_eof()
            with self.assertRaisesRegex(ValueError, "message length"):
                await wire.read_message(reader)

        asyncio.run(check())


if __name__ == "__main__":
    unittest.main()
