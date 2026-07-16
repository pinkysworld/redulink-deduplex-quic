import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

import run_ibm_registry_trace_residency_v3_17 as trace_study  # type: ignore


def record(timestamp: str, uri: str, size: int, *, client: str = "client-a") -> dict:
    return {
        "timestamp": timestamp,
        "http.request.method": "GET",
        "http.request.remoteaddr": client,
        "http.request.uri": uri,
        "http.response.status": 200,
        "http.response.written": size,
    }


class IbmRegistryTraceResidencyTests(unittest.TestCase):
    def test_streaming_json_array_handles_small_reads(self):
        source = io.StringIO(json.dumps([{"a": 1}, {"b": "two"}, {"c": [3]}]))
        self.assertEqual(
            list(trace_study.stream_json_array(source, read_size=3)),
            [{"a": 1}, {"b": "two"}, {"c": [3]}],
        )

    def test_lru_reports_hit_and_eviction(self):
        cache = trace_study.LRUCache(8)
        self.assertFalse(cache.access("a", 4)[0])
        self.assertFalse(cache.access("b", 4)[0])
        self.assertTrue(cache.access("a", 4)[0])
        hit, _delta, evicted_objects, evicted_bytes = cache.access("c", 6)
        self.assertFalse(hit)
        self.assertEqual(evicted_objects, 2)
        self.assertEqual(evicted_bytes, 8)
        self.assertEqual(cache.resident_bytes, 6)

    def test_shard_merge_and_byte_budgets_change_residency(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "data_centers" / "dc-a"
            root.mkdir(parents=True)
            shard_zero = [
                record("2017-06-20T00:00:01.000Z", "v2/r/blobs/a", 4),
                record("2017-06-20T00:00:03.000Z", "v2/r/blobs/a", 4),
            ]
            shard_one = [
                record("2017-06-20T00:00:02.000Z", "v2/r/blobs/b", 4),
            ]
            (root / "dc-a-logstash-2017.06.20-0.json").write_text(
                json.dumps(shard_zero), encoding="utf-8",
            )
            (root / "dc-a-logstash-2017.06.20-1.json").write_text(
                json.dumps(shard_one), encoding="utf-8",
            )
            result = trace_study.analyze_trace(
                trace_root=Path(temporary),
                budgets=[4, 8],
                progress_every=0,
            )
        by_budget = {
            item["budget_bytes_per_client"]: item
            for item in result["budget_results"]
            if item["deployment_class"] == "all"
        }
        self.assertEqual(result["records_processed"], 3)
        self.assertEqual(by_budget[4]["warm_request_hits"], 0)
        self.assertEqual(by_budget[8]["warm_request_hits"], 1)
        self.assertEqual(by_budget[8]["warm_request_hit_fraction"], 0.333333)


if __name__ == "__main__":
    unittest.main()
