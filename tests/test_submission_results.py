import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def rows(name: str) -> list[dict[str, str]]:
    with (RESULTS / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class SubmissionResultTests(unittest.TestCase):
    def test_submission_result_set_is_complete(self):
        expected = {
            "aioquic_scaling_experiment.csv", "aioquic_scaling_experiment.json",
            "aioquic_workload_cases.csv", "aioquic_workload_cases.json",
            "external_object_workload_suite.csv", "external_public_suite.csv",
            "framing_dictionary_baseline.csv", "framing_dictionary_baseline.json",
            "ibm_registry_trace_residency_v3_17.csv",
            "ibm_registry_trace_residency_v3_17.json",
            "object_chunk_size_sensitivity.csv", "object_chunk_size_sensitivity.json",
            "protocol_stream_byte_accounting.csv", "protocol_stream_byte_accounting.json",
            "pypi_version_pair_object_study.csv", "pypi_version_pair_object_study.json",
            "quic_flow_comparison.csv", "quic_flow_comparison.json",
            "quic_miss_rate_sensitivity.csv", "quic_miss_rate_sensitivity.json",
            "public_registry_layer_study_v3_17.csv",
            "public_registry_layer_study_v3_17.json",
            "public_registry_layer_chunk_sensitivity_v3_17.csv",
            "public_registry_layer_chunk_sensitivity_v3_17.json",
            "cpu_throughput_scaling_v3_17.csv",
            "cpu_throughput_scaling_v3_17.json",
            "cpu_throughput_scaling_v3_17_summary.csv",
            "linux_netem_quic_path_v3_17.csv",
            "linux_netem_quic_path_v3_17.json",
            "linux_netem_quic_path_v3_17_summary.csv",
            "quic_multistream_experiment_v3_17.csv",
            "quic_multistream_experiment_v3_17.json",
            "quic_competing_fairness_v3_17.csv",
            "quic_competing_fairness_v3_17.json",
            "deployment_envelope.csv", "deployment_envelope.json",
            "rsync_baseline_external_public.csv",
        }
        self.assertEqual({path.name for path in RESULTS.iterdir() if path.is_file()}, expected)

    def test_native_committed_tables_exclude_timing_and_packet_fields(self):
        for name in [
            "quic_flow_comparison.csv",
            "aioquic_workload_cases.csv",
            "aioquic_scaling_experiment.csv",
            "quic_miss_rate_sensitivity.csv",
        ]:
            result_rows = rows(name)
            self.assertTrue(result_rows)
            columns = {column.lower() for column in result_rows[0]}
            for fragment in ["elapsed", "throughput", "udp", "ipv4", "proxy"]:
                self.assertFalse(any(fragment in column for column in columns), (name, fragment, columns))
            self.assertTrue(all(row["reconstruction_ok"] == "True" for row in result_rows))
            self.assertTrue(all(
                "live TLS 1.3 exporter" in row["redulink_key_derivation"]
                or "not applicable to raw QUIC" in row["redulink_key_derivation"]
                for row in result_rows
            ))
            self.assertTrue(any(
                "live TLS 1.3 exporter" in row["redulink_key_derivation"]
                for row in result_rows
            ))
            self.assertTrue(all(
                row["tls_exporter_live"] in {"True", "not_applicable"}
                for row in result_rows
            ))
            self.assertTrue(all(
                row["tls_exporter_outputs_match"] in {"True", "not_applicable"}
                for row in result_rows
            ))
            self.assertTrue(all(
                "EXPERIMENTAL-ReduLink-v1" in row["tls_exporter_invocation"]
                or "not applicable" in row["tls_exporter_invocation"]
                for row in result_rows
            ))
            self.assertTrue(all(
                "fixed binary" in row["record_mac_transcript"]
                or "not applicable" in row["record_mac_transcript"]
                for row in result_rows
            ))

    def test_workload_controls_include_a_negative_case(self):
        by_label = {row["label"]: row for row in rows("aioquic_workload_cases.csv")}
        self.assertEqual(set(by_label), {
            "demo-positive",
            "independent-compressed-negative",
            "external-positive-redis-layered",
        })
        self.assertLess(float(by_label["independent-compressed-negative"]["stream_payload_multiplier"]), 1.0)
        self.assertGreater(float(by_label["demo-positive"]["stream_payload_multiplier"]), 1.0)

    def test_protocol_accounting_excludes_diagnostics_from_total(self):
        data = json.loads((RESULTS / "protocol_stream_byte_accounting.json").read_text(encoding="utf-8"))
        self.assertEqual(
            data["redulink_protocol_stream_bytes"],
            data["redulink_forward_protocol_stream_bytes"] + data["redulink_reverse_repair_control_stream_bytes"],
        )
        self.assertGreater(data["redulink_diagnostic_stats_stream_bytes_excluded"], 0)

    def test_full_v3_17_transport_evidence_is_committed(self):
        netem = json.loads((RESULTS / "linux_netem_quic_path_v3_17.json").read_text())
        self.assertEqual(len(netem["summary"]), 16)
        self.assertEqual(len(netem["rows"]), 640)
        self.assertTrue(all(item["paired_rounds"] == 20 for item in netem["summary"]))
        self.assertTrue(all(row["reconstruction_ok"] for row in netem["rows"]))
        self.assertTrue(all(
            row["measurement_control_stream_bytes_excluded"] == 13
            for row in netem["rows"]
        ))

        streams = json.loads(
            (RESULTS / "quic_multistream_experiment_v3_17.json").read_text()
        )
        self.assertEqual(streams["aggregate"]["rounds"], 20)
        self.assertTrue(streams["aggregate"]["all_reconstructed"])
        self.assertTrue(all(
            mode["actual_stream_ids"] == [0, 4, 8, 12, 16]
            for mode in streams["modes"]
        ))

        fairness = json.loads(
            (RESULTS / "quic_competing_fairness_v3_17.json").read_text()
        )
        self.assertEqual({item["case"] for item in fairness["summary"]}, {
            "raw-raw", "redulink-redulink", "raw-redulink",
        })
        self.assertTrue(all(item["rounds"] == 20 for item in fairness["summary"]))
        self.assertTrue(all(item["all_reconstructed"] for item in fairness["summary"]))


if __name__ == "__main__":
    unittest.main()
