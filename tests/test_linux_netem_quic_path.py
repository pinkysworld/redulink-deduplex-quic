import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

import run_linux_netem_quic_path as netem  # type: ignore


class LinuxNetemQuicPathTests(unittest.TestCase):
    def test_setup_command_uses_half_rtt_delay_and_rate(self):
        [cmd] = netem.setup_commands(
            device="lo",
            rate_mbps=5.0,
            rtt_ms=20.0,
            loss_percent=0.1,
            limit_packets=4096,
            use_sudo=True,
        )
        self.assertEqual(cmd[:7], ["sudo", "tc", "qdisc", "replace", "dev", "lo", "root"])
        self.assertIn("netem", cmd)
        self.assertIn("10ms", cmd)
        self.assertIn("5mbit", cmd)
        self.assertIn("0.1%", cmd)
        self.assertEqual(cmd[-2:], ["loss", "0.1%"])

    def test_cleanup_command_deletes_root_qdisc(self):
        self.assertEqual(
            netem.cleanup_commands(device="lo", use_sudo=False),
            [["tc", "qdisc", "del", "dev", "lo", "root"]],
        )

    def test_dry_run_prints_setup_and_cleanup_without_linux_requirement(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "benchmarks" / "run_linux_netem_quic_path.py"),
                "--dry-run",
                "--payload", "demo",
                "--rate-mbps", "5",
                "--rtt-ms", "20",
                "--loss-percent", "0",
                "--rounds", "1",
                "--no-sudo",
            ],
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["experiment"], "linux_netem_quic_path_dry_run")
        self.assertEqual(payload["measurement_mode"], "isolated")
        self.assertEqual(payload["setup"][0][:6], ["tc", "qdisc", "replace", "dev", "lo", "root"])
        self.assertEqual(payload["cleanup"], [["tc", "qdisc", "del", "dev", "lo", "root"]])

    def test_summary_reports_bootstrap_columns(self):
        rows = [
            {
                "payload": "demo",
                "rate_mbps": 5.0,
                "rtt_ms": 20.0,
                "loss_percent": 0.0,
                "round": i,
                "method": "raw-quic-stream",
                "completion_ms_measured": 10.0,
                "encoded_stream_payload_bytes": 1000,
                "reconstructed_bytes": 1000,
                "reconstruction_ok": True,
            }
            for i in range(1, 4)
        ]
        rows.extend(
            {
                "payload": "demo",
                "rate_mbps": 5.0,
                "rtt_ms": 20.0,
                "loss_percent": 0.0,
                "round": i,
                "method": "redulink-binary-quic-stream",
                "completion_ms_measured": 8.0,
                "encoded_stream_payload_bytes": 250,
                "reconstructed_bytes": 1000,
                "reconstruction_ok": True,
            }
            for i in range(1, 4)
        )
        [summary] = netem.summarize(rows)
        self.assertEqual(summary["rounds"], 3)
        self.assertEqual(summary["completion_ratio_mean"], 0.8)
        self.assertEqual(summary["encoded_byte_ratio_mean"], 0.25)
        self.assertIn("completion_ratio_ci95_low", summary)


if __name__ == "__main__":
    unittest.main()


class LinuxNetemCommittedResultTests(unittest.TestCase):
    """Validate the committed live-netem result (produced in a rootless netns)."""

    def test_committed_netem_result_is_wellformed(self):
        import csv
        csv_p = ROOT / "results" / "linux_netem_quic_path.csv"
        json_p = ROOT / "results" / "linux_netem_quic_path.json"
        if not csv_p.exists() or not json_p.exists():
            self.skipTest("live netem result not present; run run_linux_netem_quic_path.py on Linux")
        with csv_p.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertGreaterEqual(len(rows), 8)
        for r in rows:
            self.assertEqual(r["reconstruction_ok"], "True")
            self.assertIn("tc/netem", r["emulation"])
            self.assertGreater(float(r["completion_ms_measured"]), 0.0)
        data = json.loads(json_p.read_text())
        self.assertEqual(data["experiment"], "linux_netem_quic_path")
        for s in data["summary"]:
            self.assertTrue(s["all_reconstructed"])
            self.assertGreaterEqual(s["rounds"], 10)
            self.assertIn("completion_ratio_ci95_low", s)
            # ReduLink sends strictly fewer encoded bytes than raw on the wire
            self.assertLess(s["encoded_byte_ratio_mean"], 1.0)


if __name__ == "__main__":
    unittest.main()
