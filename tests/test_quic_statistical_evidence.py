import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "benchmarks"))

import summarize_quic_statistical_evidence as qstats  # type: ignore


class QuicStatisticalEvidenceTests(unittest.TestCase):
    def test_emulated_path_summary_uses_paired_raw_and_redulink_rows(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "emulated.csv"
            csv_path.write_text(
                "payload,rate_mbps,rtt_ms,loss_every,round,method,input_bytes,"
                "encoded_stream_payload_bytes,reconstructed_bytes,completion_ms_measured,"
                "reconstruction_ok\n"
                "demo,5,20,0,1,raw-quic-stream,100,100,100,10,True\n"
                "demo,5,20,0,1,redulink-binary-quic-stream,100,50,100,5,True\n"
                "demo,5,20,0,2,raw-quic-stream,100,100,100,20,True\n"
                "demo,5,20,0,2,redulink-binary-quic-stream,100,50,100,10,True\n",
                encoding="utf-8",
            )
            rows = qstats.emulated_path_rows(csv_path)

        ratio = next(r for r in rows if r["metric"] == "completion_ratio_redulink_over_raw")
        encoded = next(r for r in rows if r["metric"] == "encoded_byte_ratio_redulink_over_raw")
        multiplier = next(r for r in rows if r["metric"] == "redulink_stream_multiplier")
        self.assertEqual(ratio["n"], 2)
        self.assertEqual(ratio["mean"], 0.5)
        self.assertEqual(encoded["mean"], 0.5)
        self.assertEqual(multiplier["mean"], 2.0)


if __name__ == "__main__":
    unittest.main()
