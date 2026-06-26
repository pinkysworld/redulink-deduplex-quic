#!/usr/bin/env python3
"""Check generated target-class manifests and result labels for consistency."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

import generate_target_corpora


def parse_pair_hashes(value: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in value.split(";"):
        key, item = part.strip().split("=", 1)
        parsed[key] = item
    return parsed


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="benchmarks/target_class_manifest.csv")
    parser.add_argument("--results", default="results/target_class_suite.csv")
    args = parser.parse_args()

    manifest_path = ROOT / args.manifest
    result_path = ROOT / args.results

    with manifest_path.open(newline="") as fh:
        manifest_rows = list(csv.DictReader(fh))
    expected_labels = [label for label, _, _ in generate_target_corpora.CASES]
    manifest_labels = [row["label"] for row in manifest_rows]
    if manifest_labels != expected_labels:
        raise SystemExit(f"manifest labels do not match generator: {manifest_labels} != {expected_labels}")

    for row in manifest_rows:
        warm_path = ROOT / row["warm_path"]
        update_path = ROOT / row["update_path"]
        if not warm_path.exists() or not update_path.exists():
            raise SystemExit(f"missing generated corpus files for {row['label']}")
        hashes = parse_pair_hashes(row["sha256"])
        if sha256(warm_path) != hashes["warm"]:
            raise SystemExit(f"warm hash mismatch for {row['label']}")
        if sha256(update_path) != hashes["update"]:
            raise SystemExit(f"update hash mismatch for {row['label']}")
        if len(warm_path.read_bytes()) != int(row["warm_bytes"]):
            raise SystemExit(f"warm byte-size mismatch for {row['label']}")
        if len(update_path.read_bytes()) != int(row["update_bytes"]):
            raise SystemExit(f"update byte-size mismatch for {row['label']}")

    if result_path.exists():
        with result_path.open(newline="") as fh:
            result_labels = {row["artifact"] for row in csv.DictReader(fh)}
        unknown = result_labels - set(manifest_labels)
        missing = set(manifest_labels) - result_labels
        if unknown:
            raise SystemExit(f"result CSV contains labels not in manifest: {sorted(unknown)}")
        if missing:
            raise SystemExit(f"result CSV is missing manifest labels: {sorted(missing)}")

    print("generated target-class artifacts are consistent")


if __name__ == "__main__":
    main()
