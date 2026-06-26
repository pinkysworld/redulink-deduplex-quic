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

    def test_empty_master_secret_rejected(self):
        with self.assertRaises(ValueError):
            ks.derive_redulink_secret(b"", ks.ReduLinkKeyContext(alpn="x", epoch=1, scope="s"))


if __name__ == "__main__":
    unittest.main()
