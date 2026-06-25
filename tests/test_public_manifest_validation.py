import csv
import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "public_artifacts_manifest.csv"


def parse_pair_field(value):
    parsed = {}
    for part in value.split(";"):
        label, item = part.split(":", 1)
        parsed[label] = item
    return parsed


class PublicManifestValidationTests(unittest.TestCase):
    def test_public_manifest_checksums_sizes_and_changed_pairs(self):
        with MANIFEST.open(newline="") as fh:
            rows = list(csv.DictReader(fh))

        self.assertGreaterEqual(len(rows), 3)
        changed_pairs = 0
        for row in rows:
            warm_path = ROOT / row["warm_path"]
            update_path = ROOT / row["update_path"]
            self.assertTrue(warm_path.exists(), row["label"])
            self.assertTrue(update_path.exists(), row["label"])

            hashes = parse_pair_field(row["sha256"])
            sizes = parse_pair_field(row["bytes"])
            warm_bytes = warm_path.read_bytes()
            update_bytes = update_path.read_bytes()

            self.assertEqual(hashlib.sha256(warm_bytes).hexdigest(), hashes["warm"], row["label"])
            self.assertEqual(hashlib.sha256(update_bytes).hexdigest(), hashes["update"], row["label"])
            self.assertEqual(len(warm_bytes), int(sizes["warm"]), row["label"])
            self.assertEqual(len(update_bytes), int(sizes["update"]), row["label"])
            if hashes["warm"] != hashes["update"]:
                changed_pairs += 1
                self.assertEqual(row.get("content_relation"), "changed", row["label"])

        self.assertGreaterEqual(changed_pairs, 3)


if __name__ == "__main__":
    unittest.main()
