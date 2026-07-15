import unittest

from src import redulink_key_schedule as ks


class KeyScheduleTests(unittest.TestCase):
    def test_context_separation_changes_secret(self):
        master = b"test master secret"
        ctx = ks.ReduLinkKeyContext(alpn="redulink/1", epoch=1, scope="a", connection_context=b"c")
        base = ks.derive_redulink_secret(master, ctx)
        self.assertEqual(len(base), 32)
        self.assertNotEqual(base, ks.derive_redulink_secret(master, ks.ReduLinkKeyContext(alpn="redulink/2", epoch=1, scope="a", connection_context=b"c")))
        self.assertNotEqual(base, ks.derive_redulink_secret(master, ks.ReduLinkKeyContext(alpn="redulink/1", epoch=2, scope="a", connection_context=b"c")))
        self.assertNotEqual(base, ks.derive_redulink_secret(master, ks.ReduLinkKeyContext(alpn="redulink/1", epoch=1, scope="b", connection_context=b"c")))
        self.assertNotEqual(base, ks.derive_redulink_secret(master, ks.ReduLinkKeyContext(alpn="redulink/1", epoch=1, scope="a", connection_context=b"d")))
        self.assertNotEqual(base, ks.derive_redulink_secret(master, ks.ReduLinkKeyContext(alpn="redulink/1", epoch=1, scope="a", connection_context=b"c", direction="server-to-client")))

    def test_delimiter_injection_contexts_do_not_collide(self):
        master = b"test master secret"
        first = ks.ReduLinkKeyContext(
            alpn="A", epoch=1, scope="X|epoch=2|scope=Y",
            connection_context=b"c", stream_context=b"s",
        )
        second = ks.ReduLinkKeyContext(
            alpn="A|epoch=1|scope=X", epoch=2, scope="Y",
            connection_context=b"c", stream_context=b"s",
        )
        self.assertNotEqual(ks.context_info(first), ks.context_info(second))
        self.assertNotEqual(
            ks.derive_redulink_secret(master, first),
            ks.derive_redulink_secret(master, second),
        )

    def test_context_encoding_is_unambiguous_for_binary_fields(self):
        left = ks.ReduLinkKeyContext(
            alpn="redulink/1", epoch=1, scope="scope",
            connection_context=b"a\x00b", stream_context=b"c",
        )
        right = ks.ReduLinkKeyContext(
            alpn="redulink/1", epoch=1, scope="scope",
            connection_context=b"a", stream_context=b"\x00bc",
        )
        self.assertNotEqual(ks.context_info(left), ks.context_info(right))

    def test_empty_master_secret_rejected(self):
        with self.assertRaises(ValueError):
            ks.derive_redulink_secret(b"", ks.ReduLinkKeyContext(alpn="x", epoch=1, scope="s"))


if __name__ == "__main__":
    unittest.main()
