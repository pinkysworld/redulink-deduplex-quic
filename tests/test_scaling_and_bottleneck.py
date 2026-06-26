import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AIOQUIC_AVAILABLE = importlib.util.find_spec('aioquic') is not None

class ScalingAndBottleneckTests(unittest.TestCase):
    @unittest.skipUnless(AIOQUIC_AVAILABLE, 'aioquic is not installed')
    def test_aioquic_scaling_small_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_csv = Path(tmp) / 'scaling.csv'
            out_json = Path(tmp) / 'scaling.json'
            subprocess.run([
                sys.executable, str(ROOT / 'benchmarks' / 'run_aioquic_scaling_experiment.py'),
                '--blocks', '96',
                '--output-csv', str(out_csv),
                '--output-json', str(out_json),
            ], cwd=ROOT, check=True, timeout=60)
            with out_csv.open() as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['reconstruction_ok'], 'True')
            self.assertGreater(float(rows[0]['stream_payload_multiplier']), 1.0)

    def test_bottleneck_emulation_from_flow_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_csv = Path(tmp) / 'flow.csv'
            input_csv.write_text('method,loss_every,input_bytes,stream_payload_bytes,effective_multiplier,reconstruction_ok,semantic_misses,repair_full_frames,client_elapsed_ms,proxy_dropped\nraw-quic-stream,0,98304,98304,1.0,True,0,0,10,0\nredulink-binary-quic-stream,0,98304,29793,3.299,True,13,13,20,0\n')
            out_csv = Path(tmp) / 'bottleneck.csv'
            out_json = Path(tmp) / 'bottleneck.json'
            subprocess.run([
                sys.executable, str(ROOT / 'benchmarks' / 'run_quic_bottleneck_emulation.py'),
                '--input-csv', str(input_csv),
                '--rates-mbps', '25',
                '--rtt-ms', '10',
                '--output-csv', str(out_csv),
                '--output-json', str(out_json),
            ], cwd=ROOT, check=True)
            with out_csv.open() as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 2)
            self.assertTrue(out_json.exists())
            data = json.loads(out_json.read_text())
            self.assertIn('rows', data)

if __name__ == '__main__':
    unittest.main()
