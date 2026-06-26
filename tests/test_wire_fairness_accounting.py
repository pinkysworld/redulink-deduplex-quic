import unittest
from benchmarks import run_wire_fairness_accounting as exp


class WireFairnessAccountingTests(unittest.TestCase):
    def test_redulink_competes_on_wire_bytes(self):
        result = exp.run_experiment()
        self.assertTrue(result["redulink_uses_less_wire_than_raw"])
        self.assertGreater(result["redulink_effective_app_multiplier"], 1.0)
        self.assertAlmostEqual(result["wire_share_redulink"] + result["wire_share_raw"], 1.0, places=5)
        self.assertLess(result["wire_share_redulink"], 0.5)


if __name__ == "__main__":
    unittest.main()
