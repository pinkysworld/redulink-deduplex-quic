import csv
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SubmissionEvidenceCheckerTests(unittest.TestCase):
    def run_checker(self, generated: Path, *, check: bool = True):
        return subprocess.run([
            sys.executable,
            str(ROOT / "scripts" / "check_submission_evidence.py"),
            "--generated-dir",
            str(generated),
        ], cwd=ROOT, check=check, capture_output=True, text=True)

    def copy_results(self, tmp: str) -> Path:
        generated = Path(tmp) / "results"
        shutil.copytree(ROOT / "results", generated)
        return generated

    def rewrite_rsync(self, generated: Path, mutate):
        path = generated / "rsync_baseline_external_public.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        mutate(rows[0])
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def test_committed_results_compare_to_themselves(self):
        self.run_checker(ROOT / "results")

    def test_rsync_gate_accepts_control_only_variation_below_one_percent(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated = self.copy_results(tmp)

            def vary_control_bytes(row):
                old_total = int(row["rsync_control_plus_data_bytes"])
                new_total = round(old_total * 1.008)
                rounds = int(row["rsync_rounds"])
                row["rsync_total_bytes_sent"] = str(
                    new_total - int(row["rsync_total_bytes_received"])
                )
                row["rsync_control_plus_data_bytes"] = str(new_total)
                row["rsync_control_plus_data_bytes_per_round"] = ";".join(
                    [str(new_total)] * rounds
                )
                row["rsync_control_plus_data_bytes_min"] = str(new_total)
                row["rsync_control_plus_data_bytes_max"] = str(new_total)

            self.rewrite_rsync(generated, vary_control_bytes)
            self.run_checker(generated)

    def test_rsync_gate_rejects_changed_delta_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated = self.copy_results(tmp)
            self.rewrite_rsync(
                generated,
                lambda row: row.__setitem__(
                    "rsync_literal_data", str(int(row["rsync_literal_data"]) + 1),
                ),
            )
            result = self.run_checker(generated, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("rsync_literal_data changed", result.stderr)

    def test_rsync_gate_rejects_inconsistent_round_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated = self.copy_results(tmp)
            self.rewrite_rsync(
                generated,
                lambda row: row.__setitem__("rsync_control_plus_data_bytes_min", "1"),
            )
            result = self.run_checker(generated, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("recorded minimum is inconsistent", result.stderr)


if __name__ == "__main__":
    unittest.main()
