"""CI-safe validation of the committed full-duplex path-emulation results."""
import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestQuicEmulatedPath(unittest.TestCase):
    def _check(self, stem: str, expected_payload: str):
        csv_p = ROOT / "results" / f"{stem}.csv"
        json_p = ROOT / "results" / f"{stem}.json"
        self.assertTrue(csv_p.exists() and json_p.exists(), stem)
        with csv_p.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 8)
        for r in rows:
            self.assertEqual(r["reconstruction_ok"], "True")
            self.assertGreater(float(r["completion_ms_measured"]), 0.0)
            self.assertIn("not kernel netem", r["emulation"])
            self.assertIn("per direction", r["emulation"])  # full-duplex marker
            self.assertEqual(r["payload"], expected_payload)
        data = json.loads(json_p.read_text())
        self.assertEqual(data["experiment"], "measured_fullduplex_path_emulation_competing_flows")
        for s in data["summary"]:
            self.assertTrue(s["all_reconstructed"])
            self.assertIn("raw_completion_ms_sd", s)
            self.assertGreater(s["rl_over_raw_completion"], 0.0)

    def test_demo_payload_results(self):
        self._check("quic_emulated_path", "demo")

    def test_redis_real_payload_results(self):
        self._check("quic_emulated_path_redis", "redis")

    def test_redulink_encodes_fewer_bytes_than_raw_demo(self):
        with (ROOT / "results" / "quic_emulated_path.csv").open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        raw = [int(r["encoded_stream_payload_bytes"]) for r in rows if r["method"] == "raw-quic-stream"]
        rl = [int(r["encoded_stream_payload_bytes"]) for r in rows if r["method"] != "raw-quic-stream"]
        self.assertLess(max(rl), min(raw))


if __name__ == "__main__":
    unittest.main()
