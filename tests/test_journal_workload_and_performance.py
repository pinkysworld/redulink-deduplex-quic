import csv
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path):
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


class JournalWorkloadAndPerformanceTests(unittest.TestCase):
    def test_journal_workload_suite_has_positive_and_negative_cases(self):
        path = ROOT / "results" / "journal_workload_suite.csv"
        if not path.exists():
            subprocess.run([sys.executable, "benchmarks/generate_journal_corpora.py"], cwd=ROOT, check=True)
            subprocess.run([
                sys.executable, "benchmarks/run_baseline_comparison.py",
                "--manifest", "benchmarks/journal_workload_manifest.csv",
                "--family", "journal-fixture",
                "--output", "results/journal_workload_suite.csv",
                "--chunk-size", "4096",
            ], cwd=ROOT, check=True)
        rows = read_csv(path)
        warm_rl = [r for r in rows if r["mode"] == "warm-update-like" and r["method"] == "redulink"]
        self.assertTrue(any(float(r["effective_multiplier"]) > 5 for r in warm_rl))
        self.assertTrue(any(r["artifact"] == "independent-compressed-negative" and float(r["effective_multiplier"]) <= 1.01 for r in warm_rl))

    def test_component_performance_results_have_required_components(self):
        path = ROOT / "results" / "component_performance.csv"
        if not path.exists():
            subprocess.run([sys.executable, "benchmarks/run_component_performance.py", "--size", "524288"], cwd=ROOT, check=True)
        rows = read_csv(path)
        components = {r["component"] for r in rows}
        self.assertIn("fixed_chunking", components)
        self.assertIn("cdc_chunking", components)
        self.assertIn("binary_wire_encode", components)

    @unittest.skipIf(importlib.util.find_spec("aioquic") is None, "aioquic not installed")
    def test_quic_flow_comparison_results_or_smoke_run(self):
        path = ROOT / "results" / "quic_flow_comparison.csv"
        if not path.exists():
            subprocess.run([sys.executable, "benchmarks/run_quic_flow_comparison.py", "--loss-every", "0"], cwd=ROOT, check=True)
        rows = read_csv(path)
        raw = next(r for r in rows if r["method"] == "raw-quic-stream" and r["loss_every"] == "0")
        rl = next(r for r in rows if r["method"] == "redulink-binary-quic-stream" and r["loss_every"] == "0")
        self.assertEqual(raw["reconstruction_ok"], "True")
        self.assertEqual(rl["reconstruction_ok"], "True")
        self.assertGreater(float(rl["effective_multiplier"]), 1.0)


if __name__ == "__main__":
    unittest.main()
