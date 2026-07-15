import unittest
from benchmarks import run_protocol_stream_accounting as exp


class ProtocolStreamAccountingTests(unittest.TestCase):
    def test_same_layer_directional_accounting(self):
        raw = {
            "input_bytes": "98304", "stream_payload_bytes": "98304",
            "forward_protocol_stream_bytes": "98304",
            "reverse_repair_control_stream_bytes": "0",
            "diagnostic_stats_stream_bytes": "240", "reconstruction_ok": "True",
        }
        redulink = {
            "input_bytes": "98304", "stream_payload_bytes": "32000",
            "forward_protocol_stream_bytes": "31700",
            "reverse_repair_control_stream_bytes": "300",
            "diagnostic_stats_stream_bytes": "800", "reconstruction_ok": "True",
        }
        result = exp.summarize(raw, redulink)
        self.assertTrue(result["redulink_uses_fewer_protocol_stream_bytes"])
        self.assertGreater(result["redulink_protocol_multiplier"], 1.0)
        self.assertAlmostEqual(
            result["raw_byte_share_in_pair"] + result["redulink_byte_share_in_pair"],
            1.0,
            places=5,
        )
        self.assertIn("does not establish", result["claim_scope"])


if __name__ == "__main__":
    unittest.main()
