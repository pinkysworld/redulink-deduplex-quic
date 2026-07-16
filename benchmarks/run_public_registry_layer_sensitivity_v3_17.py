#!/usr/bin/env python3
"""Run pinned registry-layer reuse at several fixed chunk sizes.

This wrapper invokes the digest-verifying primary layer study once per chunk
size, retains the 4 KiB result as the primary artifact, and combines all rows
into a sensitivity artifact. Blob downloads remain in the external cache.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_SCRIPT = ROOT / "benchmarks" / "run_public_registry_layer_study_v3_17.py"


def combine_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        raise ValueError("at least one component result is required")
    labels = [str(row["label"]) for row in results[0]["rows"]]
    combined_rows = []
    aggregate_by_chunk_size = []
    component_provenance = []
    for result in results:
        chunk_size = int(result["parameters"]["chunk_size_bytes"])
        if [str(row["label"]) for row in result["rows"]] != labels:
            raise ValueError("component result labels or order differ")
        if not bool(result["aggregate"]["all_reconstructed"]):
            raise ValueError(f"component reconstruction failed at {chunk_size} bytes")
        combined_rows.extend(result["rows"])
        aggregate_by_chunk_size.append({
            "chunk_size_bytes": chunk_size,
            **result["aggregate"],
        })
        component_provenance.append({
            "chunk_size_bytes": chunk_size,
            "retrieved_at_utc": result["retrieved_at_utc"],
            "provenance": result["provenance"],
        })
    return {
        "experiment": "pinned_public_registry_layer_chunk_sensitivity_v3_17",
        "scope": results[0]["scope"],
        "registry_api": results[0]["registry_api"],
        "registry": results[0]["registry"],
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "chunk_sizes_bytes": [
            int(result["parameters"]["chunk_size_bytes"])
            for result in results
        ],
        "aggregate_by_chunk_size": aggregate_by_chunk_size,
        "rows": combined_rows,
        "pinned_manifests": results[0]["pinned_manifests"],
        "component_provenance": component_provenance,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path,
        default=ROOT / "benchmarks" / "public_registry_layer_manifest_v3_17.csv",
    )
    parser.add_argument(
        "--cache", type=Path,
        default=Path("/tmp/redulink-public-registry-layer-cache-v3-17"),
    )
    parser.add_argument("--chunk-sizes", type=int, nargs="+", default=[1024, 4096, 16384])
    parser.add_argument(
        "--primary-output-json", type=Path,
        default=ROOT / "results" / "public_registry_layer_study_v3_17.json",
    )
    parser.add_argument(
        "--primary-output-csv", type=Path,
        default=ROOT / "results" / "public_registry_layer_study_v3_17.csv",
    )
    parser.add_argument(
        "--output-json", type=Path,
        default=ROOT / "results" / "public_registry_layer_chunk_sensitivity_v3_17.json",
    )
    parser.add_argument(
        "--output-csv", type=Path,
        default=ROOT / "results" / "public_registry_layer_chunk_sensitivity_v3_17.csv",
    )
    args = parser.parse_args()
    sizes = list(dict.fromkeys(args.chunk_sizes))
    if any(size < 512 for size in sizes):
        raise SystemExit("chunk sizes must be at least 512 bytes")
    if 4096 not in sizes:
        raise SystemExit("chunk sizes must include the primary 4096-byte point")

    component_results = []
    with tempfile.TemporaryDirectory(prefix="redulink-registry-sensitivity-") as temporary:
        temp = Path(temporary)
        for size in sizes:
            output_json = (
                args.primary_output_json if size == 4096
                else temp / f"registry-{size}.json"
            )
            output_csv = (
                args.primary_output_csv if size == 4096
                else temp / f"registry-{size}.csv"
            )
            subprocess.run([
                sys.executable,
                str(PRIMARY_SCRIPT),
                "--manifest", str(args.manifest),
                "--cache", str(args.cache),
                "--chunk-size", str(size),
                "--output-json", str(output_json),
                "--output-csv", str(output_csv),
            ], cwd=ROOT, check=True)
            component_results.append(json.loads(output_json.read_text(encoding="utf-8")))

    combined = combine_results(component_results)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(combined["rows"][0]), lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(combined["rows"])
    print(args.output_json)


if __name__ == "__main__":
    main()
