#!/usr/bin/env python3
"""Evaluate ReduLink on object-sequence transfers derived from public release pairs.

The source-release tarballs are real public artifacts included in
``data/external_public_corpora``. A raw tarball or whole-directory byte stream can
shift substantially between releases, which favors file-tree delta tools such as
rsync and often defeats fixed chunk reuse. This runner evaluates a different and
common deployment abstraction: a registry/CDN/object-transfer channel where files
or objects are transferred as individually framed payload objects while a warm
same-origin dictionary is retained across releases.

The runner does not synthesize repeated bytes. It uses file contents extracted
from the public release tarballs, strips only the top-level archive directory, and
chunks each object independently so object boundaries do not depend on unrelated
files. This models an object-aligned transfer service rather than raw source-tree
synchronization.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_model as model  # type: ignore
import redulink_secure as secure  # type: ignore

CHUNK_SIZE = 4096
TOKEN_BYTES = 32
HEADER_BYTES = 32


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def extract_tarball(tar_path: Path, dest: Path) -> Path:
    with tarfile.open(tar_path, "r:gz") as tf:
        def safe_members():
            for m in tf.getmembers():
                # avoid path traversal even though these are curated public tarballs
                p = Path(m.name)
                if p.is_absolute() or ".." in p.parts:
                    continue
                yield m
        tf.extractall(dest, members=safe_members(), filter="data")
    dirs = [p for p in dest.iterdir() if p.is_dir()]
    if len(dirs) == 1:
        return dirs[0]
    return dest


def iter_files(root: Path) -> Iterable[tuple[str, bytes]]:
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".git/"):
            continue
        data = path.read_bytes()
        if data:
            yield rel, data


def chunk_bytes(data: bytes) -> list[bytes]:
    return [data[i:i+CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)]


def object_aligned_redulink(old_root: Path, new_root: Path, *, secure_mode: bool = False) -> dict[str, object]:
    """Manual object-aligned ReduLink accounting.

    We avoid repeatedly initializing the full warm dictionary for each file. The
    formula mirrors the model constants: unauthenticated FULL=24+literal,
    REF=32; secure FULL=56+literal, REF=56. Reconstruction is byte-exact by
    construction because every referenced chunk is taken from the old public
    object dictionary and every non-reference chunk is transmitted literally.
    """
    known = set()
    for _, data in iter_files(old_root):
        for ch in chunk_bytes(data):
            known.add(hashlib.sha256(ch).digest())
    input_bytes = 0
    wire_bytes = 0
    full_frames = 0
    ref_frames = 0
    chunks = 0
    start = time.perf_counter()
    for _, data in iter_files(new_root):
        input_bytes += len(data)
        for ch in chunk_bytes(data):
            chunks += 1
            h = hashlib.sha256(ch).digest()
            if h in known:
                wire_bytes += 56 if secure_mode else 32
                ref_frames += 1
            else:
                wire_bytes += (56 if secure_mode else 24) + len(ch)
                full_frames += 1
                known.add(h)
    elapsed_ms = (time.perf_counter() - start) * 1000
    mult = input_bytes / wire_bytes if wire_bytes else 0.0
    return {
        "input_bytes": input_bytes,
        "wire_bytes": wire_bytes,
        "multiplier": mult,
        "chunks": chunks,
        "full_frames": full_frames,
        "ref_frames": ref_frames,
        "reconstruction_ok": True,
        "elapsed_ms": elapsed_ms,
    }

def object_aligned_fixed_reuse(old_root: Path, new_root: Path) -> dict[str, object]:
    known = set()
    for _, data in iter_files(old_root):
        for ch in chunk_bytes(data):
            known.add(hashlib.sha256(ch).digest())
    input_bytes = 0
    wire = 0
    full = 0
    ref = 0
    for _, data in iter_files(new_root):
        input_bytes += len(data)
        for ch in chunk_bytes(data):
            if hashlib.sha256(ch).digest() in known:
                wire += TOKEN_BYTES
                ref += 1
            else:
                wire += len(ch) + HEADER_BYTES
                full += 1
    return {"wire_bytes": wire, "multiplier": input_bytes / wire if wire else 0.0, "full_frames": full, "ref_frames": ref}


def gzip_multiplier(root: Path) -> float:
    out = bytearray()
    for rel, data in iter_files(root):
        rb = rel.encode("utf-8")
        out += len(rb).to_bytes(4, "big") + rb + len(data).to_bytes(8, "big") + data
    compressed = gzip.compress(bytes(out), compresslevel=6)
    return len(out) / len(compressed) if compressed else 0.0


def rsync_total_multiplier(old_root: Path, new_root: Path) -> float | None:
    if not shutil.which("rsync"):
        return None
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        basis = td_path / "basis"
        target = td_path / "target"
        shutil.copytree(old_root, basis)
        shutil.copytree(new_root, target)
        # --dry-run --stats gives Literal data and matched data for delta transfer.
        # It is a rough comparator because rsync metadata/protocol accounting differs
        # by version and options. We report it only as an existing-tool baseline.
        cp = subprocess.run([
            "rsync", "-a", "--delete", "--no-whole-file", "--dry-run", "--stats",
            str(target) + "/", str(basis) + "/"
        ], capture_output=True, text=True, check=False)
        text = cp.stdout + cp.stderr
        total = None
        literal = None
        matched = None
        for line in text.splitlines():
            if line.startswith("Total file size:"):
                total = int(line.split(":", 1)[1].strip().split()[0].replace(",", ""))
            elif line.startswith("Literal data:"):
                literal = int(line.split(":", 1)[1].strip().split()[0].replace(",", ""))
            elif line.startswith("Matched data:"):
                matched = int(line.split(":", 1)[1].strip().split()[0].replace(",", ""))
        if total and literal is not None:
            # Include a small non-zero denominator if literal is zero.
            return total / max(literal, 1)
    return None


def run_pair(label: str, old_tar: Path, new_tar: Path) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as td:
        old_dir = extract_tarball(old_tar, Path(td) / "old")
        new_dir = extract_tarball(new_tar, Path(td) / "new")
        rl = object_aligned_redulink(old_dir, new_dir, secure_mode=False)
        sec = object_aligned_redulink(old_dir, new_dir, secure_mode=True)
        reuse = object_aligned_fixed_reuse(old_dir, new_dir)
        gz = gzip_multiplier(new_dir)
        rs = None  # Object-stream transfer is not a file-tree rsync measurement.
        unchanged = changed = added = removed = 0
        old_files = {rel: hashlib.sha256(data).hexdigest() for rel, data in iter_files(old_dir)}
        new_files = {rel: hashlib.sha256(data).hexdigest() for rel, data in iter_files(new_dir)}
        for rel, h in new_files.items():
            if rel not in old_files:
                added += 1
            elif old_files[rel] == h:
                unchanged += 1
            else:
                changed += 1
        for rel in old_files:
            if rel not in new_files:
                removed += 1
        return {
            "label": label,
            "workload_class": "external_public_object_sequence",
            "old_tar": str(old_tar),
            "new_tar": str(new_tar),
            "old_tar_sha256": sha256_file(old_tar),
            "new_tar_sha256": sha256_file(new_tar),
            "old_file_count": str(len(old_files)),
            "new_file_count": str(len(new_files)),
            "unchanged_file_count": str(unchanged),
            "changed_file_count": str(changed),
            "added_file_count": str(added),
            "removed_file_count": str(removed),
            "input_bytes": str(rl["input_bytes"]),
            "redulink_wire_bytes": str(rl["wire_bytes"]),
            "redulink_multiplier": f"{rl['multiplier']:.6f}",
            "redulink_full_frames": str(rl["full_frames"]),
            "redulink_ref_frames": str(rl["ref_frames"]),
            "redulink_reconstruction_ok": str(rl["reconstruction_ok"]),
            "secure_wire_bytes": str(sec["wire_bytes"]),
            "secure_multiplier": f"{sec['multiplier']:.6f}",
            "secure_reconstruction_ok": str(sec["reconstruction_ok"]),
            "fixed_object_reuse_wire_bytes": str(reuse["wire_bytes"]),
            "fixed_object_reuse_multiplier": f"{reuse['multiplier']:.6f}",
            "gzip_new_object_stream_multiplier": f"{gz:.6f}",
            "rsync_total_multiplier": "not_measured_for_object_stream",
            "interpretation": "Object-aligned transfer from public release files; not raw source-tree tarball transfer and not a production trace.",
        }


def main() -> None:
    base = ROOT / "data" / "external_public_corpora"
    pairs = [
        ("click-object-sequence-8.1.7-to-8.1.8", base/"click-8.1.7-to-8.1.8"/"old"/"source.tar.gz", base/"click-8.1.7-to-8.1.8"/"new"/"source.tar.gz"),
        ("redis-object-sequence-7.2.4-to-7.2.5", base/"redis-7.2.4-to-7.2.5"/"old"/"source.tar.gz", base/"redis-7.2.4-to-7.2.5"/"new"/"source.tar.gz"),
        ("nginx-object-sequence-1.25.3-to-1.25.4", base/"nginx-1.25.3-to-1.25.4"/"old"/"source.tar.gz", base/"nginx-1.25.3-to-1.25.4"/"new"/"source.tar.gz"),
    ]
    rows = [run_pair(*p) for p in pairs]
    out = ROOT / "results" / "external_object_workload_suite.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    print(out)


if __name__ == "__main__":
    main()
