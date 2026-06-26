#!/usr/bin/env python3
"""Fetch pinned external public release snapshots for journal evaluation.

The package's scripted fixtures are deterministic and useful for offline review,
but journal reviewers also expect independently curated public inputs. This
script downloads small/medium public source-release archives, extracts them, and
writes a manifest consumable by run_real_workload_manifest.py.
"""

from __future__ import annotations

import csv
import hashlib
import io
import tarfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "external_public_corpora"
MANIFEST = ROOT / "benchmarks" / "external_public_manifest.csv"

PAIRS = [
    {
        "label": "click-8.1.7-to-8.1.8",
        "workload": "external-python-package-release",
        "old_url": "https://codeload.github.com/pallets/click/tar.gz/refs/tags/8.1.7",
        "new_url": "https://codeload.github.com/pallets/click/tar.gz/refs/tags/8.1.8",
    },
    {
        "label": "redis-7.2.4-to-7.2.5",
        "workload": "external-server-source-release",
        "old_url": "https://codeload.github.com/redis/redis/tar.gz/refs/tags/7.2.4",
        "new_url": "https://codeload.github.com/redis/redis/tar.gz/refs/tags/7.2.5",
    },
    {
        "label": "nginx-1.25.3-to-1.25.4",
        "workload": "external-network-server-release",
        "old_url": "https://codeload.github.com/nginx/nginx/tar.gz/refs/tags/release-1.25.3",
        "new_url": "https://codeload.github.com/nginx/nginx/tar.gz/refs/tags/release-1.25.4",
    },
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def extract_tar_gz(blob: bytes, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        tf.extractall(dest, filter="data")
    roots = [item for item in dest.iterdir() if item.is_dir()]
    if len(roots) != 1:
        raise RuntimeError(f"expected one root directory in {dest}, found {roots}")
    return roots[0]


def materialize(label: str, side: str, url: str) -> tuple[Path, int, str]:
    archive_dir = OUT / label / side
    root = archive_dir / "tree"
    if root.exists():
        # Reuse existing extraction and preserve the real downloaded archive hash.
        source_root = next(root.iterdir())
        archive = archive_dir / "source.tar.gz"
        if archive.exists():
            blob = archive.read_bytes()
            return source_root, len(blob), sha256(blob)
        blob = fetch(url)
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(blob)
        (archive_dir / "source.sha256").write_text(sha256(blob) + "  source.tar.gz\n", encoding="utf-8")
        return source_root, len(blob), sha256(blob)

    blob = fetch(url)
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "source.tar.gz").write_bytes(blob)
    source_root = extract_tar_gz(blob, root)
    (archive_dir / "source.sha256").write_text(sha256(blob) + "  source.tar.gz\n", encoding="utf-8")
    return source_root, len(blob), sha256(blob)


def main() -> None:
    rows: list[dict[str, str]] = []
    for pair in PAIRS:
        old_root, old_archive_bytes, old_archive_sha = materialize(pair["label"], "old", pair["old_url"])
        new_root, new_archive_bytes, new_archive_sha = materialize(pair["label"], "new", pair["new_url"])
        rows.append({
            "label": pair["label"],
            "workload": pair["workload"],
            "old_path": str(old_root.relative_to(ROOT)),
            "new_path": str(new_root.relative_to(ROOT)),
            "chunker": "fixed",
            "chunk_size": "4096",
            "old_url": pair["old_url"],
            "new_url": pair["new_url"],
            "old_archive_bytes": str(old_archive_bytes),
            "new_archive_bytes": str(new_archive_bytes),
            "old_archive_sha256": old_archive_sha,
            "new_archive_sha256": new_archive_sha,
            "license_note": "Public GitHub source release snapshots; see upstream repositories for project licenses.",
        })

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(MANIFEST)


if __name__ == "__main__":
    main()
