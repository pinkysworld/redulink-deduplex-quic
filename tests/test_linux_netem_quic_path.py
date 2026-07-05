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
