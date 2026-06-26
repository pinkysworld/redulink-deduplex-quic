#!/usr/bin/env python3
"""Run ReduLink and baseline methods on user-supplied real workload pairs.

The CSV manifest must contain at least: label,old_path,new_path. Optional fields
are workload,mode,chunker,chunk_size. Paths may point to files or directories.
Directories are read in deterministic sorted order. This runner is intended for
journal revisions where reviewers or authors add OCI layers, package updates,
repository snapshots, VM images, or structured-log corpora without changing the
artifact code.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_model as model  # type: ignore
import redulink_secure as secure  # type: ignore
import redulink_wire as wire  # type: ignore


def read_bytes(path: Path) -> bytes:
    if path.is_file():
        return path.read_bytes()
    if path.is_dir():
        out = bytearray()
        for item in sorted(p for p in path.rglob("*") if p.is_file()):
            rel = str(item.relative_to(path)).replace("\\", "/").encode("utf-8")
            data = item.read_bytes()
            out += len(rel).to_bytes(4, "big") + rel + len(data).to_bytes(8, "big") + data
        return bytes(out)
    raise FileNotFoundError(path)


def fixed_block_reuse(old: bytes, new: bytes, *, chunk_size: int) -> int:
    """Simple exact-block reuse approximation used by the manifest runner.

    This intentionally differs from `run_baseline_comparison.py`'s byte-scanning
    fixed-block comparator. Here each update block either emits a 32-byte
    reference token or a 32-byte literal header plus literal bytes. The result is
    a coarse exact-block sanity check, not rsync and not the journal fixture's
    coalesced-literal baseline.
    """
    known = {hashlib.sha256(old[i:i + chunk_size]).digest() for i in range(0, len(old), chunk_size)}
    wire = 0
    for i in range(0, len(new), chunk_size):
        chunk = new[i:i + chunk_size]
        if hashlib.sha256(chunk).digest() in known:
            wire += 32
        else:
            wire += len(chunk) + 32
    return wire


def run_one(row: dict[str, str]) -> dict[str, str]:
    label = row.get("label") or row.get("workload") or "workload"
    old_path = Path(row["old_path"])
    new_path = Path(row["new_path"])
    chunker = row.get("chunker", "fixed") or "fixed"
    chunk_size = int(row.get("chunk_size", "4096") or 4096)
    old = read_bytes(old_path)
    new = read_bytes(new_path)
    started = time.perf_counter()
    stats = model.run_bytes(new, warm=old, chunker=chunker, chunk_size=chunk_size)
    elapsed_ms = (time.perf_counter() - started) * 1000
    secure_started = time.perf_counter()
    secure_stats = secure.run_bytes(new, warm_dictionary=old, chunker=chunker, chunk_size=chunk_size)
    secure_elapsed_ms = (time.perf_counter() - secure_started) * 1000
    reuse_wire = fixed_block_reuse(old, new, chunk_size=chunk_size)
    return {
        "label": label,
        "workload": row.get("workload", label),
        "old_path": str(old_path),
        "new_path": str(new_path),
        "old_bytes": str(len(old)),
        "new_bytes": str(len(new)),
        "old_sha256": hashlib.sha256(old).hexdigest(),
        "new_sha256": hashlib.sha256(new).hexdigest(),
        "chunker": chunker,
        "chunk_size": str(chunk_size),
        "redulink_wire_bytes": str(stats.wire_bytes),
        "redulink_multiplier": f"{stats.effective_multiplier:.6f}",
        "redulink_reconstruction_ok": str(stats.reconstruction_ok),
        "secure_wire_bytes": str(secure_stats.wire_bytes),
        "secure_multiplier": f"{secure_stats.effective_multiplier:.6f}",
        "secure_reconstruction_ok": str(secure_stats.reconstruction_ok),
        "fixed_block_reuse_wire_bytes": str(reuse_wire),
        "fixed_block_reuse_multiplier": f"{(len(new) / reuse_wire) if reuse_wire else 0:.6f}",
        "fixed_block_reuse_parameters": "exact 4096-byte block membership; 32-byte match token; 32-byte literal header per block; no rolling checksum; not rsync",
        "redulink_elapsed_ms": f"{elapsed_ms:.3f}",
        "secure_elapsed_ms": f"{secure_elapsed_ms:.3f}",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, default=ROOT / "results" / "real_workload_suite.csv")
    args = p.parse_args()
    with args.manifest.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit("manifest has no rows")
    out_rows = [run_one(r) for r in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()), lineterminator="\n")
        writer.writeheader(); writer.writerows(out_rows)
    print(args.output)


if __name__ == "__main__":
    main()
