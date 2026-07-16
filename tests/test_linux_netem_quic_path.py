import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

import run_linux_netem_quic_path as netem  # type: ignore


class LinuxNetemQuicPathTests(unittest.TestCase):
    def test_setup_uses_half_rtt_rate_limit_and_loss(self):
        [command] = netem.setup_commands(
            device="lo",
            rate_mbps=5.0,
            rtt_ms=20.0,
            loss_percent=0.5,
            limit_packets=4096,
            use_sudo=True,
        )
        self.assertEqual(command[:7], ["sudo", "tc", "qdisc", "replace", "dev", "lo", "root"])
        self.assertIn("10ms", command)
        self.assertIn("5mbit", command)
        self.assertEqual(command[-2:], ["loss", "0.5%"])

    def test_parse_qdisc_counters_prefers_root_netem(self):
        payload = json.dumps([
            {"kind": "fq_codel", "stats": {"bytes": 999, "packets": 99}},
            {
                "kind": "netem",
                "root": True,
                "stats": {
                    "bytes": 12000,
                    "packets": 31,
                    "drops": 2,
                    "overlimits": 4,
                    "requeues": 1,
                },
            },
        ])
        self.assertEqual(netem.parse_qdisc_counters(payload), {
            "bytes": 12000,
            "packets": 31,
            "drops": 2,
            "overlimits": 4,
            "requeues": 1,
        })

    def test_counter_delta_is_non_negative(self):
        before = {name: 10 for name in netem.COUNTER_NAMES}
        after = {name: (15 if name != "drops" else 8) for name in netem.COUNTER_NAMES}
        delta = netem.counter_delta(before, after)
        self.assertEqual(delta["bytes"], 5)
        self.assertEqual(delta["drops"], 0)

    def test_dry_run_is_available_without_linux(self):
        process = subprocess.run(
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
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(process.stdout)
        self.assertEqual(result["experiment"], "linux_netem_quic_path_v3_17_dry_run")
        self.assertEqual(result["setup"][0][:6], ["tc", "qdisc", "replace", "dev", "lo", "root"])
        self.assertEqual(result["cleanup"], [["tc", "qdisc", "del", "dev", "lo", "root"]])

    def test_context_always_captures_and_cleans_up(self):
        completed = subprocess.CompletedProcess(["tc"], 0, stdout="[]", stderr="")
        snapshots = [
            ({name: 0 for name in netem.COUNTER_NAMES}, "before"),
            ({name: 1 for name in netem.COUNTER_NAMES}, "after"),
        ]
        with patch.object(netem, "_run", return_value=completed) as run_mock:
            with patch.object(netem, "qdisc_counters", side_effect=snapshots):
                with netem.netem_context(
                    device="lo",
                    rate_mbps=5.0,
                    rtt_ms=20.0,
                    loss_percent=0.0,
                    limit_packets=4096,
                    use_sudo=False,
                ) as state:
                    self.assertEqual(state["qdisc_json_before"], "before")
                self.assertEqual(state["qdisc_json_after"], "after")
        commands = [call.args[0] for call in run_mock.call_args_list]
        self.assertIn(["tc", "qdisc", "del", "dev", "lo", "root"], commands)

    def test_paired_summary_has_bootstrap_intervals_for_each_axis(self):
        rows = []
        for round_id in range(1, 5):
            common = {
                "payload": "demo",
                "rate_mbps": 5.0,
                "rtt_ms": 20.0,
                "loss_percent": 0.0,
                "round": round_id,
                "reconstruction_ok": True,
                "congestion_control_algorithm": "reno",
            }
            rows.append({
                **common,
                "method": "raw-quic-stream",
                "client_completion_ms": 100.0,
                "client_ttfb_ms": 20.0,
                "server_completion_ms": 80.0,
                "combined_endpoint_process_cpu_ms": 12.0,
                "encoded_stream_payload_bytes": 1000,
                "qdisc_bytes": 1500,
                "qdisc_packets": 20,
            })
            rows.append({
                **common,
                "method": "redulink-binary-quic-stream",
                "client_completion_ms": 60.0,
                "client_ttfb_ms": 15.0,
                "server_completion_ms": 45.0,
                "combined_endpoint_process_cpu_ms": 18.0,
                "encoded_stream_payload_bytes": 400,
                "qdisc_bytes": 900,
                "qdisc_packets": 14,
            })
        [summary] = netem.summarize(rows)
        self.assertEqual(summary["paired_rounds"], 4)
        self.assertEqual(summary["client_completion_ratio_mean"], 0.6)
        self.assertEqual(summary["process_cpu_ratio_mean"], 1.5)
        self.assertIn("qdisc_packets_ratio_ci95_low", summary)
        self.assertTrue(summary["all_reconstructed"])


if __name__ == "__main__":
    unittest.main()
