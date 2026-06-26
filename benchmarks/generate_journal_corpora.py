#!/usr/bin/env python3
"""Generate deterministic journal-evaluation fixtures.

The package cannot download large external artifacts during review. These
fixtures are therefore scripted and deterministic: they model the structure of
workload classes that reviewers expect (disk snapshots, OCI-like layers,
package metadata, repository snapshots, and structured logs) while preserving
exact reproducibility and small package size. The benchmark runner records them
as scripted fixtures, not production traces.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import os
import random
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "journal_corpora"
DEFAULT_MANIFEST = ROOT / "benchmarks" / "journal_workload_manifest.csv"


def stable_bytes(label: str, size: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < size:
        out.extend(hashlib.sha256(f"{label}:{counter}".encode()).digest())
        counter += 1
    return bytes(out[:size])


def write_pair(root: Path, name: str, warm: bytes, update: bytes) -> tuple[Path, Path]:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    warm_path = d / "warm.bin"
    update_path = d / "update.bin"
    warm_path.write_bytes(warm)
    update_path.write_bytes(update)
    return warm_path, update_path


def disk_snapshot_pair() -> tuple[bytes, bytes]:
    # 256 fixed pages with sparse changed pages and zero regions, similar to a
    # simple block-image backup fixture.
    pages = []
    for i in range(256):
        if i % 16 == 0:
            pages.append(b"\0" * 4096)
        else:
            prefix = f"disk-page-{i:04d}:".encode()
            pages.append(prefix + stable_bytes(f"disk-{i}", 4096 - len(prefix)))
    warm_pages = list(pages)
    update_pages = list(pages)
    for i in [3, 17, 48, 79, 121, 190, 221]:
        prefix = f"disk-page-{i:04d}-changed:".encode()
        update_pages[i] = prefix + stable_bytes(f"disk-change-{i}", 4096 - len(prefix))
    return b"".join(warm_pages), b"".join(update_pages)


def oci_like_layer_pair() -> tuple[bytes, bytes]:
    def make_tar(version: int) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for i in range(96):
                content = (f"/app/file_{i:03d}.txt\n".encode() + stable_bytes(f"oci-common-{i}", 2048))
                if version == 2 and i in {7, 11, 40, 66, 91}:
                    content = (f"/app/file_{i:03d}.txt\nchanged\n".encode() + stable_bytes(f"oci-change-{i}", 2048))
                info = tarfile.TarInfo(name=f"app/file_{i:03d}.txt")
                info.size = len(content)
                info.mtime = 1
                info.uid = info.gid = 0
                info.uname = info.gname = "root"
                tar.addfile(info, io.BytesIO(content))
        return buf.getvalue()
    return make_tar(1), make_tar(2)


def package_metadata_pair() -> tuple[bytes, bytes]:
    base = []
    for i in range(5000):
        base.append(f"Package: libdemo-{i}\nVersion: 1.{i % 23}.{i % 7}\nArchitecture: amd64\nDescription: deterministic package metadata {i % 97}\n\n")
    warm = "".join(base).encode()
    update_lines = base[:]
    for i in range(0, 5000, 431):
        update_lines[i] = f"Package: libdemo-{i}\nVersion: 2.{i % 23}.{i % 7}\nArchitecture: amd64\nDescription: deterministic package metadata updated {i % 97}\n\n"
    update = "".join(update_lines).encode()
    return warm, update


def repo_snapshot_pair() -> tuple[bytes, bytes]:
    def make_snapshot(version: int) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for i in range(160):
                body = []
                for j in range(64):
                    body.append(f"def function_{i}_{j}():\n    return {i*j + version if i in {12, 55, 101} else i*j}\n\n")
                content = "".join(body).encode()
                info = tarfile.TarInfo(name=f"src/module_{i:03d}.py")
                info.size = len(content)
                info.mtime = 1
                tar.addfile(info, io.BytesIO(content))
        return buf.getvalue()
    return make_snapshot(1), make_snapshot(2)


def structured_log_pair() -> tuple[bytes, bytes]:
    warm = []
    update = []
    for i in range(50000):
        warm.append(f"2026-06-26T12:{i%60:02d}:00Z level=INFO service=api tenant={i%200} op=login status=200 latency={i%97}\n")
        if i % 777 == 0:
            update.append(f"2026-06-26T12:{i%60:02d}:00Z level=WARN service=api tenant={i%200} op=login status=503 latency={200+i%97}\n")
        else:
            update.append(warm[-1])
    return "".join(warm).encode(), "".join(update).encode()


def independent_compressed_pair() -> tuple[bytes, bytes]:
    warm = gzip.compress(stable_bytes("independent-compressed-a", 262144), compresslevel=6, mtime=0)
    update = gzip.compress(stable_bytes("independent-compressed-b", 262144), compresslevel=6, mtime=0)
    return warm, update


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, maker, notes in [
        ("scripted-disk-snapshot", disk_snapshot_pair, "scripted page-aligned disk snapshot fixture"),
        ("scripted-oci-layer", oci_like_layer_pair, "scripted OCI-like tar layer fixture with stable tar metadata"),
        ("scripted-package-metadata", package_metadata_pair, "scripted package metadata version fixture"),
        ("scripted-repository-snapshot", repo_snapshot_pair, "scripted repository snapshot tar fixture"),
        ("scripted-structured-logs", structured_log_pair, "scripted structured log update fixture"),
        ("independent-compressed-negative", independent_compressed_pair, "independent compressed negative control"),
    ]:
        warm, update = maker()
        warm_path, update_path = write_pair(args.out_dir, name, warm, update)
        rows.append({
            "label": name,
            "warm_path": str(warm_path.relative_to(ROOT)),
            "update_path": str(update_path.relative_to(ROOT)),
            "warm_sha256": hashlib.sha256(warm).hexdigest(),
            "update_sha256": hashlib.sha256(update).hexdigest(),
            "warm_bytes": len(warm),
            "update_bytes": len(update),
            "notes": notes,
        })
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(args.manifest)


if __name__ == "__main__":
    main()
