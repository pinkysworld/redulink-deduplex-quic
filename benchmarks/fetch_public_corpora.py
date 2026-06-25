#!/usr/bin/env python3
"""Fetch pinned public corpora for ReduLink benchmark smoke results."""

from __future__ import annotations

import argparse
import csv
import hashlib
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class PublicPair:
    label: str
    source_url: str
    warm_url: str
    update_url: str
    license_note: str


PAIRS = [
    PublicPair(
        label="cpython-http-server",
        source_url="https://github.com/python/cpython",
        warm_url="https://raw.githubusercontent.com/python/cpython/v3.11.0/Lib/http/server.py",
        update_url="https://raw.githubusercontent.com/python/cpython/v3.12.0/Lib/http/server.py",
        license_note="Python Software Foundation License",
    ),
    PublicPair(
        label="cpython-pathlib",
        source_url="https://github.com/python/cpython",
        warm_url="https://raw.githubusercontent.com/python/cpython/v3.11.0/Lib/pathlib.py",
        update_url="https://raw.githubusercontent.com/python/cpython/v3.12.0/Lib/pathlib.py",
        license_note="Python Software Foundation License",
    ),
    PublicPair(
        label="linux-kernel-parameters",
        source_url="https://github.com/torvalds/linux",
        warm_url="https://raw.githubusercontent.com/torvalds/linux/v6.8/Documentation/admin-guide/kernel-parameters.txt",
        update_url="https://raw.githubusercontent.com/torvalds/linux/v6.9/Documentation/admin-guide/kernel-parameters.txt",
        license_note="GPL-2.0-only documentation in Linux source tree",
    ),
    PublicPair(
        label="nginx-changes",
        source_url="https://github.com/nginx/nginx",
        warm_url="https://raw.githubusercontent.com/nginx/nginx/release-1.25.0/docs/xml/nginx/changes.xml",
        update_url="https://raw.githubusercontent.com/nginx/nginx/release-1.25.1/docs/xml/nginx/changes.xml",
        license_note="2-clause BSD-like nginx license",
    ),
    PublicPair(
        label="redis-readme",
        source_url="https://github.com/redis/redis",
        warm_url="https://raw.githubusercontent.com/redis/redis/7.2/README.md",
        update_url="https://raw.githubusercontent.com/redis/redis/7.4/README.md",
        license_note="BSD-3-Clause for Redis 7.2; Redis 7.4 source is RSALv2/SSPLv1/AGPLv3 tri-licensed",
    ),
    PublicPair(
        label="ietf-quic-rfc",
        source_url="https://www.rfc-editor.org/",
        warm_url="https://www.rfc-editor.org/rfc/rfc9000.txt",
        update_url="https://www.rfc-editor.org/rfc/rfc9001.txt",
        license_note="RFC Editor Trust legal provisions",
    ),
]


def fetch(url: str, path: Path) -> tuple[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest(), len(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/public_corpora")
    parser.add_argument("--manifest", default="benchmarks/public_artifacts_manifest.csv")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    retrieved = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = []
    for pair in PAIRS:
        warm_path = out_dir / pair.label / "warm.txt"
        update_path = out_dir / pair.label / "update.txt"
        warm_sha, warm_bytes = fetch(pair.warm_url, warm_path)
        update_sha, update_bytes = fetch(pair.update_url, update_path)
        rows.append({
            "label": pair.label,
            "source_url": pair.source_url,
            "warm_url": pair.warm_url,
            "update_url": pair.update_url,
            "warm_path": str(warm_path),
            "update_path": str(update_path),
            "path": "",
            "sha256": f"warm:{warm_sha};update:{update_sha}",
            "bytes": f"warm:{warm_bytes};update:{update_bytes}",
            "content_relation": "identical" if warm_sha == update_sha else "changed",
            "license_note": pair.license_note,
            "retrieved_utc": retrieved,
        })

    manifest = Path(args.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(manifest)


if __name__ == "__main__":
    main()
