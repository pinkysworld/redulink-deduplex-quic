from __future__ import annotations

import unittest

from cryptography.hazmat.primitives import hashes

from src import redulink_key_schedule as key_schedule
from src import redulink_tls_exporter as exporter


class TlsExporterTests(unittest.TestCase):
    def test_private_label_and_version_gate_are_explicit(self):
        self.assertEqual(exporter.EXPORTER_LABEL, key_schedule.DEFAULT_LABEL)
        self.assertTrue(exporter.EXPORTER_LABEL.startswith(b"EXPERIMENTAL"))
        self.assertEqual(exporter.SUPPORTED_AIOQUIC_VERSION, "1.3.0")
        exporter.install_aioquic_exporter_bridge()
        exporter.install_aioquic_exporter_bridge()

    def test_fixed_exporter_vector(self):
        output = exporter.export_keying_material_from_secret(
            exporter_master_secret=bytes(range(32)),
            label=exporter.EXPORTER_LABEL,
            context_value=bytes.fromhex(
                "02494e778a899b9ba6153eaeb319720d"
                "992df585977b47d644a98149829627ea"
            ),
            length=32,
            algorithm=hashes.SHA256(),
        )
        self.assertEqual(
            output.hex(),
            "b5ad0d24c2f69defec788216f58b01b2"
            "00d1a0fab036b9b004287fe5e9a1c322",
        )

    def test_invalid_exporter_inputs_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "printable ASCII"):
            exporter.export_keying_material_from_secret(
                exporter_master_secret=b"secret",
                label=b"bad\x00label",
                context_value=b"context",
                length=32,
            )
        with self.assertRaisesRegex(ValueError, "between 1 and 65535"):
            exporter.export_keying_material_from_secret(
                exporter_master_secret=b"secret",
                label=exporter.EXPORTER_LABEL,
                context_value=b"context",
                length=0,
            )


if __name__ == "__main__":
    unittest.main()
