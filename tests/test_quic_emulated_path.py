"""CI-safe validation of the committed measured path-emulation results."""
import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "results" / "quic_emulated_path.csv"
JSON = ROOT / "results" / "quic_emulated_path.json"


class TestQuicEmulatedPath(unittest.TestCase):
    def test_committed_results_are_wellformed(self):
        self.assertTrue(CSV.exists() and JSON.exists())
        with CSV.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 8)  # >= 4 scenarios x 2 methods
        for r in rows:
            self.assertEqual(r["reconstruction_ok"], "True")
            self.assertGreater(float(r["completion_ms_measured"]), 0.0)
            self.assertGreater(int(r["encoded_stream_payload_bytes"]), 0)
            self.assertIn("not kernel netem", r["emulation"])
        data = json.loads(JSON.read_text())
        self.assertEqual(data["experiment"], "measured_userspace_path_emulation_competing_flows")
        for s in data["summary"]:
            self.assertTrue(s["all_reconstructed"])
            # ReduLink must never be reported as reconstructing fewer bytes
            self.assertGreater(s["redulink_app_rate_mbps_mean"], 0.0)

    def test_redulink_encodes_fewer_bytes_than_raw(self):
        with CSV.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        raw = [int(r["encoded_stream_payload_bytes"]) for r in rows if r["method"] == "raw-quic-stream"]
        rl = [int(r["encoded_stream_payload_bytes"]) for r in rows if r["method"] != "raw-quic-stream"]
        self.assertLess(max(rl), min(raw))


if __name__ == "__main__":
    unittest.main()
