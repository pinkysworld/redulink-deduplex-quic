#!/usr/bin/env python3
"""Generate deterministic target-class warm/update fixtures.

These fixtures are controlled corpora for reviewer-visible baselines. They are
not a substitute for independently fetched production traces, but they exercise
the paper's claimed workload classes with reproducible byte-level context.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "target_corpora"
DEFAULT_MANIFEST = ROOT / "benchmarks" / "target_class_manifest.csv"
RNG = random.Random(0x5EED_2026)

HEADER = [
    "label",
    "target_class",
    "source_url",
    "warm_url",
    "update_url",
    "warm_path",
    "update_path",
    "path",
    "sha256",
    "warm_bytes",
    "update_bytes",
    "content_relation",
    "license_note",
    "retrieved_utc",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deterministic_noise(size: int, seed: int) -> bytes:
    rng = random.Random(seed)
    return bytes(rng.randrange(0, 256) for _ in range(size))


def mutate_spans(data: bytearray, *, seed: int, count: int, span: int) -> None:
    rng = random.Random(seed)
    if not data:
        return
    for _ in range(count):
        start = rng.randrange(0, max(1, len(data) - span))
        replacement = deterministic_noise(min(span, len(data) - start), rng.randrange(1 << 30))
        data[start:start + len(replacement)] = replacement


def software_update_pair() -> tuple[bytes, bytes, str]:
    records = []
    for package in range(6200):
        records.append(
            f"pkg=lib{package % 140:03d}; version=1.{package % 27}.{package % 19}; "
            f"arch=x86_64; dep=core{package % 83:02d}; file=/usr/lib/lib{package % 140:03d}.so\n"
        )
    warm = "".join(records).encode()
    update_records = records[:]
    for idx in range(0, len(update_records), 31):
        update_records[idx] = update_records[idx].replace("version=1.", "version=2.", 1)
    update = "".join(update_records[:2800]).encode()
    update += b"SECURITY-NOTICE CVE-2026 synthetic patch metadata\n" * 750
    update += "".join(update_records[2800:]).encode()
    return warm, update, "package metadata update with repeated records and inserted patch notices"


def container_layer_pair() -> tuple[bytes, bytes, str]:
    files = []
    for image_file in range(2800):
        body = (
            f"/app/service/{image_file % 240:03d}.py\n"
            f"def handler_{image_file % 240:03d}(event):\n"
            f"    return 'tenant={image_file % 97}; status=ok; bucket={image_file % 13}'\n"
        ).encode()
        files.append(body * (1 + (image_file % 3)))
    warm = b"".join(files)
    update_files = files[:]
    for idx in range(50, len(update_files), 113):
        update_files[idx] = update_files[idx].replace(b"status=ok", b"status=patched")
    update = b"".join(update_files[:900])
    update += b"/app/build/new-layer-marker\n" + deterministic_noise(128 * 1024, 42)
    update += b"".join(update_files[900:])
    return warm, update, "container-like layer update with mostly stable files and one new binary blob"


def git_packlike_pair() -> tuple[bytes, bytes, str]:
    blobs = []
    for obj in range(3600):
        header = f"object {obj:06d}\ntree synthetic\n".encode()
        body = (
            f"fn feature_{obj % 180}() -> usize {{ {obj % 4096} }}\n"
            f"// repeated implementation line {obj % 73}\n"
        ).encode()
        blobs.append(header + body * (2 + (obj % 4)))
    warm = b"".join(blobs)
    update = bytearray(warm)
    mutate_spans(update, seed=77, count=180, span=96)
    update[350_000:350_000] = b"commit synthetic\nparent old\nmessage: add generated feature\n" * 1100
    return warm, bytes(update), "git-packlike object stream with localized edits and inserted commits"


def vm_backup_pair() -> tuple[bytes, bytes, str]:
    block_size = 4096
    blocks = []
    for idx in range(900):
        if idx % 11 == 0:
            blocks.append(deterministic_noise(block_size, idx))
        else:
            blocks.append((f"FSBLOCK {idx % 37:02d} user-data journal-slot={idx % 19}\n".encode()).ljust(block_size, b"\0"))
    warm = b"".join(blocks)
    update_blocks = blocks[:]
    for idx in range(25, len(update_blocks), 89):
        update_blocks[idx] = deterministic_noise(block_size, 50_000 + idx)
    for idx in range(410, 430):
        update_blocks[idx] = (b"SNAPSHOT-METADATA " + str(idx).encode()).ljust(block_size, b"\0")
    return warm, b"".join(update_blocks), "VM/backup-like block image with sparse changed blocks"


def structured_logs_pair() -> tuple[bytes, bytes, str]:
    warm_lines = []
    for idx in range(45_000):
        warm_lines.append(
            f"ts=2026-06-24T12:{idx % 60:02d}:{idx % 60:02d}Z service=api tenant={idx % 512} "
            f"route=/v1/order/{idx % 23} status={200 if idx % 67 else 503} latency_ms={idx % 140}\n"
        )
    update_lines = warm_lines[:]
    for idx in range(0, len(update_lines), 97):
        update_lines[idx] = update_lines[idx].replace("status=200", "status=429")
    update_lines.extend(
        f"ts=2026-06-24T13:{idx % 60:02d}:{idx % 60:02d}Z service=api tenant={idx % 512} "
        f"route=/v1/order/{idx % 23} status=200 latency_ms={idx % 140}\n"
        for idx in range(10_000)
    )
    return "".join(warm_lines).encode(), "".join(update_lines).encode(), "structured log rollover with stable templates and fresh tail"


def random_negative_pair() -> tuple[bytes, bytes, str]:
    warm = deterministic_noise(2 * 1024 * 1024, 9101)
    update = deterministic_noise(2 * 1024 * 1024, 9102)
    return warm, update, "independent random byte streams as negative control"


def compressed_related_pair() -> tuple[bytes, bytes, str]:
    warm_source = b"".join(
        f"compressible-row={idx % 1000}; field={idx % 31}; value={idx % 17}\n".encode()
        for idx in range(80_000)
    )
    update_source = warm_source + b"small appended change\n" * 800
    warm = zlib.compress(warm_source, level=6)
    update = zlib.compress(update_source, level=6)
    return warm, update, "pre-compressed streams from related plaintext; intentionally not a negative control"


def independent_compressed_negative_pair() -> tuple[bytes, bytes, str]:
    warm = zlib.compress(deterministic_noise(768 * 1024, 12001), level=6)
    update = zlib.compress(deterministic_noise(768 * 1024, 12002), level=6)
    return warm, update, "independent compressed random streams as true compression negative control"


CASES = [
    ("software-update-generated", "software-update", software_update_pair),
    ("container-layer-generated", "container-layer", container_layer_pair),
    ("git-packlike-generated", "git-workload", git_packlike_pair),
    ("vm-backup-generated", "backup-vm", vm_backup_pair),
    ("structured-logs-generated", "logs", structured_logs_pair),
    ("random-negative-generated", "negative-control", random_negative_pair),
    ("compressed-related-warm-generated", "compressed-related", compressed_related_pair),
    ("independent-compressed-negative-generated", "negative-control", independent_compressed_negative_pair),
]


def write_case(out_dir: Path, label: str, target_class: str,
               warm: bytes, update: bytes, relation: str) -> dict[str, str]:
    case_dir = out_dir / label
    case_dir.mkdir(parents=True, exist_ok=True)
    warm_path = case_dir / "warm.bin"
    update_path = case_dir / "update.bin"
    warm_path.write_bytes(warm)
    update_path.write_bytes(update)
    return {
        "label": label,
        "target_class": target_class,
        "source_url": "generated:benchmarks/generate_target_corpora.py",
        "warm_url": "generated:deterministic-warm",
        "update_url": "generated:deterministic-update",
        "warm_path": str(warm_path.relative_to(ROOT)),
        "update_path": str(update_path.relative_to(ROOT)),
        "path": "",
        "sha256": f"warm={sha256(warm)}; update={sha256(update)}",
        "warm_bytes": str(len(warm)),
        "update_bytes": str(len(update)),
        "content_relation": relation,
        "license_note": "generated deterministic fixture; no third-party content",
        "retrieved_utc": "generated-deterministic",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    manifest = Path(args.manifest)
    if not manifest.is_absolute():
        manifest = ROOT / manifest

    rows = []
    for label, target_class, factory in CASES:
        warm, update, relation = factory()
        rows.append(write_case(out_dir, label, target_class, warm, update, relation))

    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(manifest)


if __name__ == "__main__":
    main()
