import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

import run_macos_dummynet_quic_path as dummynet  # type: ignore


class MacOSDummynetQuicPathTests(unittest.TestCase):
    def test_anchor_uses_macos_dummynet_anchor_point(self):
        self.assertEqual(dummynet.ANCHOR, "com.apple/redulink_dummynet")

    def test_pf_rules_shape_udp_on_selected_loopback_interface(self):
        rules = dummynet.pf_rules(pipe_in=123, pipe_out=456, interface="lo0", ports=[44330])
        self.assertNotIn("pipe 123", rules)
        self.assertIn(
            "dummynet out quick on lo0 inet proto udp from 127.0.0.1 to 127.0.0.1 port 44330 pipe 456",
            rules,
        )

    def test_pf_rules_can_shape_both_loopback_directions(self):
        rules = dummynet.pf_rules(
            pipe_in=123,
            pipe_out=456,
            interface="lo0",
            direction="both",
            ports=[44330],
        )
        self.assertIn(
            "dummynet in quick on lo0 inet proto udp from 127.0.0.1 port 44330 to 127.0.0.1 pipe 123",
            rules,
        )
        self.assertIn(
            "dummynet out quick on lo0 inet proto udp from 127.0.0.1 to 127.0.0.1 port 44330 pipe 456",
            rules,
        )

    def test_setup_and_cleanup_commands_are_specific_to_temp_anchor(self):
        rules_path = Path("/tmp/example-redulink-dummynet.pf")
        setup = dummynet.setup_commands(
            rate_mbps=5.0,
            rtt_ms=20.0,
            loss_percent=0.1,
            rules_path=rules_path,
        )
        self.assertEqual(setup[0], [
            "sudo", "dnctl", "pipe", str(dummynet.PIPE_IN),
            "config", "bw", "5.0Mbit/s", "delay", "10.0ms", "queue", "512Kbytes",
            "plr", "0.001000",
        ])
        self.assertEqual(setup[2], ["sudo", "pfctl", "-E"])
        self.assertEqual(setup[3], [
            "sudo", "pfctl", "-a", "com.apple/redulink_dummynet", "-f", str(rules_path),
        ])

        cleanup = dummynet.cleanup_commands()
        self.assertEqual(cleanup[0], ["sudo", "pfctl", "-a", "com.apple/redulink_dummynet", "-F", "all"])
        self.assertEqual(cleanup[1], ["sudo", "dnctl", "pipe", str(dummynet.PIPE_IN), "delete"])

    def test_summary_reports_bootstrap_ci_and_reconstruction_status(self):
        rows = [
            {
                "payload": "demo",
                "rate_mbps": 5.0,
                "rtt_ms": 20.0,
                "loss_percent": 0.1,
                "rl_over_raw_completion": 1.1,
                "encoded_byte_ratio_rl_over_raw": 0.5,
                "redulink_stream_multiplier": 2.0,
                "semantic_misses": 3,
                "all_reconstructed": True,
            },
            {
                "payload": "demo",
                "rate_mbps": 5.0,
                "rtt_ms": 20.0,
                "loss_percent": 0.1,
                "rl_over_raw_completion": 1.3,
                "encoded_byte_ratio_rl_over_raw": 0.7,
                "redulink_stream_multiplier": 1.5,
                "semantic_misses": 1,
                "all_reconstructed": True,
            },
        ]
        [summary] = dummynet.summarize(rows)
        self.assertEqual(summary["rounds"], 2)
        self.assertEqual(summary["rl_over_raw_completion_mean"], 1.2)
        self.assertIn("rl_over_raw_completion_ci95_low", summary)
        self.assertIn("encoded_byte_ratio_ci95_high", summary)
        self.assertTrue(summary["all_reconstructed"])

    def test_dry_run_cli_does_not_require_aioquic(self):
        proc = subprocess.run([
            sys.executable,
            "benchmarks/run_macos_dummynet_quic_path.py",
            "--dry-run",
            "--payload", "demo",
            "--rate-mbps", "5",
            "--rtt-ms", "20",
            "--loss-percent", "0.1",
            "--rounds", "1",
            "--raw-server-port", "49330",
            "--redulink-server-port", "49331",
        ], cwd=ROOT, text=True, capture_output=True, check=True)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["experiment"], "macos_dummynet_quic_path_dry_run")
        [dry_run] = payload["dry_runs"]
        self.assertEqual(dry_run["payload"], "demo")
        self.assertEqual(dry_run["raw_server_port"], 49330)
        self.assertEqual(dry_run["redulink_server_port"], 49331)
        self.assertIn("com.apple/redulink_dummynet", json.dumps(dry_run["setup"]))


if __name__ == "__main__":
    unittest.main()
