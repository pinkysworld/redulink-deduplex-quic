#!/usr/bin/env python3
"""Sweep the authenticated public-object profile across fixed chunk sizes.

The dictionary budget is held at 64 MiB in byte terms so that changing the
chunk size does not silently change retained warm-state capacity. Every row
performs binary frame and object-header serialization and exact reconstruction.
"""
from __future__ import annotations

import argparse
import csv
import json
import tempfile
from pathlib import Path

from run_external_object_workload_suite import (
    ROOT,
    extract_tarball,
    object_aligned_redulink,
)

CHUNK_SIZES = [512, 1024, 2048, 4096, 8192, 16384]
DICTIONARY_BUDGET_BYTES = 64 * 1024 * 1024


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk-sizes", type=int, nargs="+", default=CHUNK_SIZES)
    parser.add_argument(
        "--output-csv", type=Path,
        default=ROOT / "results" / "object_chunk_size_sensitivity.csv",
    )
    parser.add_argument(
        "--output-json", type=Path,
        default=ROOT / "results" / "object_chunk_size_sensitivity.json",
    )
    args = parser.parse_args()
    if any(size < 1 for size in args.chunk_sizes):
        raise SystemExit("chunk sizes must be positive")

    base = ROOT / "data" / "external_public_corpora"
    pairs = [
        ("click", "click-8.1.7-to-8.1.8"),
        ("redis", "redis-7.2.4-to-7.2.5"),
        ("nginx", "nginx-1.25.3-to-1.25.4"),
    ]
    rows: list[dict[str, object]] = []
    for label, directory in pairs:
        old_tar = base / directory / "old" / "source.tar.gz"
        new_tar = base / directory / "new" / "source.tar.gz"
        if not old_tar.exists() or not new_tar.exists():
            raise SystemExit("run benchmarks/fetch_external_public_corpora.py first")
        with tempfile.TemporaryDirectory(prefix=f"redulink-chunks-{label}-") as tmp:
            old_root = extract_tarball(old_tar, Path(tmp) / "old")
            new_root = extract_tarball(new_tar, Path(tmp) / "new")
            for chunk_size in args.chunk_sizes:
                budget_chunks = max(1, DICTIONARY_BUDGET_BYTES // chunk_size)
                result = object_aligned_redulink(
                    old_root,
                    new_root,
                    secure_mode=True,
                    dictionary_budget_chunks=budget_chunks,
                    chunk_size=chunk_size,
                )
                row = {
                    "label": label,
                    "release_pair": directory,
                    "chunk_size_bytes": chunk_size,
                    "dictionary_budget_bytes": DICTIONARY_BUDGET_BYTES,
                    "dictionary_budget_chunks": budget_chunks,
                    "input_bytes": result["input_bytes"],
                    "wire_bytes": result["wire_bytes"],
                    "multiplier": round(float(result["multiplier"]), 6),
                    "full_frames": result["full_frames"],
                    "ref_frames": result["ref_frames"],
                    "reconstruction_ok": result["reconstruction_ok"],
                    "wire_serialization_ok": result["wire_serialization_ok"],
                    "object_header_serialization_ok": result["object_header_serialization_ok"],
                    "authentication_key_provenance": result["authentication_key_provenance"],
                }
                if not all(bool(row[name]) for name in (
                    "reconstruction_ok", "wire_serialization_ok",
                    "object_header_serialization_ok",
                )):
                    raise RuntimeError(f"chunk-size row failed exactness: {label} {chunk_size}")
                rows.append(row)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    args.output_json.write_text(json.dumps({
        "experiment": "public_object_chunk_size_sensitivity",
        "controlled_dictionary_budget_bytes": DICTIONARY_BUDGET_BYTES,
        "rows": rows,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output_csv)


if __name__ == "__main__":
    main()
