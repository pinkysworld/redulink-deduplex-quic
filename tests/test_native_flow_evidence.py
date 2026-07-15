import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NativeFlowEvidenceTests(unittest.TestCase):
    def test_committed_zero_loss_rows_are_exact_and_same_layer(self):
        csv_path = ROOT / "results" / "quic_flow_comparison.csv"
        json_path = ROOT / "results" / "quic_flow_comparison.json"
        with csv_path.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 2)
        by_method = {row["method"]: row for row in rows}
        raw = by_method["raw-quic-stream"]
        redulink = by_method["redulink-binary-quic-stream"]
        for row in rows:
            self.assertEqual(row["loss_every"], "0")
            self.assertEqual(row["reconstruction_ok"], "True")
            self.assertEqual(row["tls_server_certificate_verified"], "True")
            self.assertEqual(row["tls_client_certificate_used"], "False")
            self.assertGreaterEqual(int(row["application_stream_id"]), 0)
        self.assertEqual(int(raw["stream_payload_bytes"]), int(raw["input_bytes"]))
        self.assertGreater(float(redulink["effective_multiplier"]), 1.0)
        evidence = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(evidence["experiment"], "zero_loss_aioquic_protocol_stream_accounting")
        self.assertEqual(evidence["results"], rows)


if __name__ == "__main__":
    unittest.main()
