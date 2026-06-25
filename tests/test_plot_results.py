import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLOT = ROOT / "scripts" / "plot_results.py"
SELECTED = ROOT / "results" / "paper_real_artifact_cdc_selected.csv"


class PlotResultsTests(unittest.TestCase):
    def test_selected_measurement_schema_can_be_plotted(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.check_call([sys.executable, str(PLOT), str(SELECTED), "--output-dir", tmp])
            out = Path(tmp)
            self.assertTrue((out / "effective_multiplier_by_workload.png").exists())
            self.assertTrue((out / "savings_by_workload.png").exists())
            self.assertTrue((out / "benchmark_summary.md").exists())


if __name__ == "__main__":
    unittest.main()
