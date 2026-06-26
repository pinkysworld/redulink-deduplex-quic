import unittest
from prototypes import redulink_authenticated_udp_experiment as exp


class AuthenticatedUdpExperimentTests(unittest.TestCase):
    def test_authenticated_udp_repair_and_negative_probes(self):
        warm, data = exp.demo_payload()
        result = exp.run_experiment(warm=warm, data=data, missing_fraction=0.25)
        self.assertTrue(result["reconstruction_ok"])
        self.assertGreater(result["semantic_misses"], 0)
        self.assertGreater(result["client_repair_full_frames"], 0)
        self.assertEqual(result["tamper_probe_rejections"], 1)
        self.assertEqual(result["replay_probe_rejections"], 1)
        self.assertEqual(result["auth_failures"], 1)
        self.assertEqual(result["replay_rejections"], 1)


if __name__ == "__main__":
    unittest.main()
