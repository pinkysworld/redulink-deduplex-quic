#!/usr/bin/env python3
"""Generate a small external-positive layered corpus from included public release data.

The corpus is derived from independently fetched public Redis release trees that are
already included in data/external_public_corpora.  It is not a production container
trace.  It is a reproducible, externally sourced, layer-like positive case: most
blocks are stable public release bytes, while a small tail layer changes.  This
models a registry/CDN transfer in which an endpoint has a prior same-origin layer
and receives a related object with large unchanged layer regions.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_OLD = ROOT / "data/external_public_corpora/redis-7.2.4-to-7.2.5/old/tree/redis-7.2.4"
SRC_NEW = ROOT / "data/external_public_corpora/redis-7.2.4-to-7.2.5/new/tree/redis-7.2.5"
OUT_DIR = ROOT / "data/external_positive_corpora/redis-layered-public-positive"
MANIFEST = ROOT / "benchmarks/external_positive_manifest.csv"
CHUNK = 4096


def file_payload(tree: Path, limit: int = 80) -> bytes:
    parts: list[bytes] = []
    files = [p for p in sorted(tree.rglob("*")) if p.is_file() and p.stat().st_size > 0]
    # Prefer real source and metadata files with stable public bytes.
    preferred = [p for p in files if p.suffix.lower() in {".c", ".h", ".md", ".conf", ".txt"}]
    for p in (preferred or files)[:limit]:
        rel = str(p.relative_to(tree)).replace('\\', '/').encode()
        data = p.read_bytes()
        parts.append(len(rel).to_bytes(2, 'big') + rel + len(data).to_bytes(4, 'big') + data)
    payload = b''.join(parts)
    # Reblock to make the positive case explicit and reviewer-inspectable: it is
    # a layer-like object made of public release bytes, not random synthetic data.
    blocks = []
    for i in range(0, len(payload), CHUNK):
        block = payload[i:i+CHUNK]
        if len(block) < CHUNK:
            block += hashlib.sha256(block + b'pad').digest() * ((CHUNK - len(block)) // 32 + 1)
            block = block[:CHUNK]
        blocks.append(block)
        if len(blocks) >= 128:
            break
    return b''.join(blocks)


def main() -> None:
    if not SRC_OLD.exists() or not SRC_NEW.exists():
        raise SystemExit('external Redis release trees are missing; run fetch_external_public_corpora.py first')
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    old_layer = file_payload(SRC_OLD)
    new_layer_base = bytearray(old_layer)
    # Change a few aligned blocks using public bytes from the newer release.
    new_public = file_payload(SRC_NEW)
    for idx, block_no in enumerate([7, 19, 43, 88, 111]):
        start = block_no * CHUNK
        if start + CHUNK <= len(new_layer_base):
            repl = bytearray(new_public[idx*CHUNK:(idx+1)*CHUNK])
            if len(repl) == CHUNK:
                # Force a real changed block while keeping the content derived
                # from the newer public release bytes.
                marker = hashlib.sha256(b'redis-layer-change' + bytes([idx]) + repl[:256]).digest()
                repl[:len(marker)] = marker
                new_layer_base[start:start+CHUNK] = bytes(repl)
    old_path = OUT_DIR / 'warm.bin'
    new_path = OUT_DIR / 'update.bin'
    old_path.write_bytes(old_layer)
    new_path.write_bytes(bytes(new_layer_base))
    rows = [{
        'label': 'redis-layered-public-positive',
        'workload': 'external-public-layered-positive',
        'old_path': str(old_path.relative_to(ROOT)),
        'new_path': str(new_path.relative_to(ROOT)),
        'chunker': 'fixed',
        'chunk_size': str(CHUNK),
        'notes': 'Layer-like positive corpus derived from included public Redis release bytes; not a production trace.',
        'old_sha256': hashlib.sha256(old_layer).hexdigest(),
        'new_sha256': hashlib.sha256(bytes(new_layer_base)).hexdigest(),
        'old_bytes': str(len(old_layer)),
        'new_bytes': str(len(new_layer_base)),
    }]
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open('w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    print(MANIFEST)

if __name__ == '__main__':
    main()
