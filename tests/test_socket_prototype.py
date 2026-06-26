import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "prototypes" / "redulink_socket_prototype.py"


class SocketPrototypeTests(unittest.TestCase):
    def test_demo_reconstructs_over_socket(self):
        output = subprocess.check_output([sys.executable, str(PROTO), "demo"], text=True)
        stats = json.loads(output)
        self.assertTrue(stats["reconstruction_ok"])
        self.assertEqual(stats["server_reconstructed_bytes"], stats["input_bytes"])
        self.assertGreater(stats["ref_frames"], 0)
        self.assertLess(stats["wire_model_bytes"], stats["input_bytes"])


if __name__ == "__main__":
    unittest.main()
