import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from run_public_registry_layer_sensitivity_v3_17 import combine_results  # type: ignore


def component(chunk_size: int, fraction: float) -> dict:
    return {
        "scope": "test",
        "registry_api": "test-api",
        "registry": "test-registry",
        "retrieved_at_utc": "2026-07-16T00:00:00+00:00",
        "provenance": {"test": True},
        "parameters": {"chunk_size_bytes": chunk_size},
        "aggregate": {
            "pairs": 1,
            "matched_chunk_byte_fraction_within_changed_layers": fraction,
            "all_reconstructed": True,
        },
        "rows": [{"label": "pair", "chunk_size_bytes": chunk_size}],
        "pinned_manifests": [{"label": "pair"}],
    }


class PublicRegistryLayerSensitivityTests(unittest.TestCase):
    def test_combines_exact_component_results_by_chunk_size(self):
        result = combine_results([
            component(1024, 0.01),
            component(4096, 0.001),
            component(16384, 0.0),
        ])
        self.assertEqual(result["chunk_sizes_bytes"], [1024, 4096, 16384])
        self.assertEqual(len(result["rows"]), 3)
        self.assertEqual(len(result["aggregate_by_chunk_size"]), 3)
        self.assertTrue(all(
            aggregate["all_reconstructed"]
            for aggregate in result["aggregate_by_chunk_size"]
        ))

    def test_rejects_failed_component_reconstruction(self):
        failed = component(4096, 0.0)
        failed["aggregate"]["all_reconstructed"] = False
        with self.assertRaises(ValueError):
            combine_results([failed])


if __name__ == "__main__":
    unittest.main()
