"""Hardening tests for verify_frame: MAC-first ordering, context binding under a
valid tag, bounded replay window, and canonical field lengths."""
from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import redulink_secure as secure  # noqa: E402

SECRET = b"verify-hardening-test-secret"


def make_frame(**over):
    frames, _ = secure.encode(
        b"A" * 4096, secret=SECRET, epoch=3, scope="s", stream_id=1,
        chunker="fixed", chunk_size=4096,
    )
    frame = frames[0]
    return dataclasses.replace(frame, **over) if over else frame


class VerifyHardeningTests(unittest.TestCase):
    def _verify(self, frame, seen=None, **ctx):
        defaults = dict(expected_epoch=3, expected_scope="s",
                        expected_stream_id=1, expected_offset=0)
        defaults.update(ctx)
        secure.verify_frame(frame, secret=SECRET, seen_nonces=seen if seen is not None else set(), **defaults)

    def test_context_tamper_with_original_tag_fails_as_auth_not_context(self):
        # An attacker who flips a context field but keeps the original tag must
        # see a generic authentication failure, not a context-specific error.
        for field, value in [("epoch", 4), ("scope", "x"), ("stream_id", 2),
                             ("offset", 4096), ("length", 1), ("nonce", 99)]:
            with self.assertRaises(ValueError) as cm:
                self._verify(make_frame(**{field: value}))
            self.assertEqual(str(cm.exception), "frame authentication failed", field)

    def test_authentic_frame_in_wrong_context_is_distinguished(self):
        # A legitimately-tagged frame replayed into the wrong expected context
        # fails the context check (after the MAC has verified).
        with self.assertRaises(ValueError) as cm:
            self._verify(make_frame(), expected_epoch=4)
        self.assertEqual(str(cm.exception), "epoch mismatch")

    def test_replay_rejected_via_window(self):
        frame = make_frame()
        window = secure.NonceWindow(size=8)
        self._verify(frame, seen=window)
        window.add(frame.nonce)
        with self.assertRaises(ValueError) as cm:
            self._verify(frame, seen=window)
        self.assertEqual(str(cm.exception), "replayed nonce")

    def test_window_floor_rejects_ancient_nonce_and_bounds_memory(self):
        window = secure.NonceWindow(size=4)
        for n in range(1, 20):
            window.add(n)
        self.assertLessEqual(len(window), 8, "window memory must stay bounded")
        self.assertIn(1, window, "nonce below the floor must read as replayed")

    def test_non_canonical_tag_or_cid_rejected(self):
        for field, value in [("tag", "ab"), ("cid", "ab"), ("tag", "z" * 64)]:
            with self.assertRaises(ValueError) as cm:
                self._verify(make_frame(**{field: value}))
            self.assertEqual(str(cm.exception), "frame authentication failed")


if __name__ == "__main__":
    unittest.main()
