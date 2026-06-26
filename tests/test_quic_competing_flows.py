import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AIOQUIC_AVAILABLE = importlib.util.find_spec('aioquic') is not None


class QuicCompetingFlowsTests(unittest.TestCase):
    @unittest.skipUnless(AIOQUIC_AVAILABLE, 'aioquic is not installed')
    def test_competing_flow_script_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_json = Path(tmp) / "flows.json"
            out_csv = Path(tmp) / "flows.csv"
            subprocess.run([
                sys.executable,
                str(ROOT / "benchmarks" / "run_quic_competing_flows.py"),
                "--rounds", "1",
                "--loss-every", "0",
                "--output-json", str(out_json),
                "--output-csv", str(out_csv),
            ], cwd=ROOT, check=True, timeout=60)
            data = json.loads(out_json.read_text())
            self.assertTrue(data["all_reconstructed"])
            self.assertEqual(len(data["rows"]), 2)
            methods = {row["method"] for row in data["rows"]}
            self.assertIn("raw-quic-stream", methods)
            self.assertIn("redulink-binary-quic-stream", methods)


if __name__ == "__main__":
    unittest.main()
