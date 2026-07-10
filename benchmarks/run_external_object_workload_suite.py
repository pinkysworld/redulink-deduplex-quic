#!/usr/bin/env python3
"""Evaluate ReduLink on object-sequence transfers derived from public release pairs.

The source-release tarballs are real public artifacts fetched into
``data/external_public_corpora`` by ``benchmarks/fetch_external_public_corpora.py``
(they are hash-pinned but gitignored, so run the fetcher once before this suite). A raw tarball or whole-directory byte stream can
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
import hmac
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_secure as secure  # type: ignore

CHUNK_SIZE = 4096
TOKEN_BYTES = 32
HEADER_BYTES = 32
OBJECT_HEADER_FIXED_BYTES = 12
OBJECT_AUTH_TAG_BYTES = 16
SECURE_SECRET = hashlib.sha256(b"ReduLink reproducible object-suite test key v1").digest()
SECURE_SCOPE = "same-origin-object-suite-v1"


@dataclass(frozen=True)
class PlainFrame:
    kind: str
    cid: str
    length: int
    payload: bytes = b""


@dataclass(frozen=True)
class ObjectRecord:
    name: str
    length: int
    frames: tuple[PlainFrame | secure.SecureFrame, ...]
    auth_tag: bytes = b""


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
        yield rel, path.read_bytes()


def chunk_bytes(data: bytes) -> list[bytes]:
    return [data[i:i+CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)]


def _object_tag(name: str, length: int, index: int) -> bytes:
    name_bytes = name.encode("utf-8")
    fields = (
        index.to_bytes(8, "big") + len(name_bytes).to_bytes(4, "big") +
        name_bytes + length.to_bytes(8, "big")
    )
    return hmac.new(
        SECURE_SECRET, b"object-boundary\0" + fields, hashlib.sha256,
    ).digest()[:OBJECT_AUTH_TAG_BYTES]


def _stream_id(name: str) -> int:
    return int.from_bytes(hashlib.sha256(name.encode("utf-8")).digest()[:8], "big")


def _warm_dictionary(root: Path, *, secure_mode: bool) -> dict[str, bytes]:
    known: dict[str, bytes] = {}
    for _, data in iter_files(root):
        for chunk in chunk_bytes(data):
            cid = (
                secure.secure_cid(chunk, secret=SECURE_SECRET, epoch=1, scope=SECURE_SCOPE)
                if secure_mode else hashlib.sha256(chunk).hexdigest()
            )
            known[cid] = chunk
    return known


def _decode_object_records(
    records: list[ObjectRecord], *, warm_root: Path, secure_mode: bool,
) -> list[tuple[str, bytes]]:
    dictionary = _warm_dictionary(warm_root, secure_mode=secure_mode)
    seen_nonces = secure.NonceWindow()
    decoded: list[tuple[str, bytes]] = []
    names: set[str] = set()
    for index, record in enumerate(records):
        if record.name in names:
            raise ValueError("duplicate object name")
        names.add(record.name)
        if secure_mode and not hmac.compare_digest(
            record.auth_tag, _object_tag(record.name, record.length, index),
        ):
            raise ValueError("object header authentication failed")
        output = bytearray()
        expected_offset = 0
        for frame in record.frames:
            if secure_mode:
                if not isinstance(frame, secure.SecureFrame):
                    raise TypeError("secure record contains a plain frame")
                secure.verify_frame(
                    frame, secret=SECURE_SECRET, expected_epoch=1,
                    expected_scope=SECURE_SCOPE, expected_stream_id=_stream_id(record.name),
                    expected_offset=expected_offset, seen_nonces=seen_nonces,
                )
                seen_nonces.add(frame.nonce)
                cid = frame.cid
                if frame.kind == "FULL":
                    chunk = frame.payload
                    if len(chunk) != frame.length or secure.secure_cid(
                        chunk, secret=SECURE_SECRET, epoch=1, scope=SECURE_SCOPE,
                    ) != cid:
                        raise ValueError("invalid secure FULL frame")
                    dictionary[cid] = chunk
                elif frame.kind == "REF":
                    chunk = dictionary.get(cid)
                    if chunk is None or len(chunk) != frame.length or secure.secure_cid(
                        chunk, secret=SECURE_SECRET, epoch=1, scope=SECURE_SCOPE,
                    ) != cid:
                        raise ValueError("invalid secure REF frame")
                else:
                    raise ValueError("unknown secure frame kind")
            else:
                if not isinstance(frame, PlainFrame):
                    raise TypeError("plain record contains a secure frame")
                cid = frame.cid
                if frame.kind == "FULL":
                    chunk = frame.payload
                    if len(chunk) != frame.length or hashlib.sha256(chunk).hexdigest() != cid:
                        raise ValueError("invalid plain FULL frame")
                    dictionary[cid] = chunk
                elif frame.kind == "REF":
                    chunk = dictionary.get(cid)
                    if chunk is None or len(chunk) != frame.length or hashlib.sha256(chunk).hexdigest() != cid:
                        raise ValueError("invalid plain REF frame")
                else:
                    raise ValueError("unknown plain frame kind")
            output.extend(chunk)
            expected_offset += len(chunk)
        if len(output) != record.length:
            raise ValueError("object boundary length mismatch")
        decoded.append((record.name, bytes(output)))
    return decoded


def object_aligned_redulink(old_root: Path, new_root: Path, *, secure_mode: bool = False) -> dict[str, object]:
    """Encode and decode the exact ordered ``(name, bytes)`` object sequence."""
    known = _warm_dictionary(old_root, secure_mode=secure_mode)
    expected_objects = list(iter_files(new_root))
    records: list[ObjectRecord] = []
    input_bytes = wire_bytes = full_frames = ref_frames = chunks = 0
    object_header_bytes = 0
    nonce = 1
    start = time.perf_counter()
    for object_index, (name, data) in enumerate(expected_objects):
        input_bytes += len(data)
        header_bytes = OBJECT_HEADER_FIXED_BYTES + len(name.encode("utf-8"))
        if secure_mode:
            header_bytes += OBJECT_AUTH_TAG_BYTES
        object_header_bytes += header_bytes
        wire_bytes += header_bytes
        frames: list[PlainFrame | secure.SecureFrame] = []
        offset = 0
        for chunk in chunk_bytes(data):
            chunks += 1
            cid = (
                secure.secure_cid(chunk, secret=SECURE_SECRET, epoch=1, scope=SECURE_SCOPE)
                if secure_mode else hashlib.sha256(chunk).hexdigest()
            )
            if cid in known:
                kind, payload = "REF", b""
                wire_bytes += 56 if secure_mode else 32
                ref_frames += 1
            else:
                kind, payload = "FULL", chunk
                wire_bytes += (56 if secure_mode else 24) + len(chunk)
                full_frames += 1
                known[cid] = chunk
            if secure_mode:
                tag = secure.frame_tag(
                    secret=SECURE_SECRET, kind=kind, epoch=1, scope=SECURE_SCOPE,
                    stream_id=_stream_id(name), offset=offset, cid=cid,
                    length=len(chunk), nonce=nonce, payload=payload,
                )
                frames.append(secure.SecureFrame(
                    kind, 1, SECURE_SCOPE, _stream_id(name), offset, cid,
                    len(chunk), nonce, tag, payload,
                ))
                nonce += 1
            else:
                frames.append(PlainFrame(kind, cid, len(chunk), payload))
            offset += len(chunk)
        records.append(ObjectRecord(
            name=name, length=len(data), frames=tuple(frames),
            auth_tag=_object_tag(name, len(data), object_index) if secure_mode else b"",
        ))
    reconstructed = _decode_object_records(records, warm_root=old_root, secure_mode=secure_mode)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return {
        "input_bytes": input_bytes,
        "wire_bytes": wire_bytes,
        "multiplier": input_bytes / wire_bytes if wire_bytes else 0.0,
        "chunks": chunks,
        "full_frames": full_frames,
        "ref_frames": ref_frames,
        "object_count": len(records),
        "object_header_bytes": object_header_bytes,
        "reconstruction_ok": reconstructed == expected_objects,
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
    for name, data in iter_files(new_root):
        input_bytes += len(data)
        wire += OBJECT_HEADER_FIXED_BYTES + len(name.encode("utf-8"))
        for ch in chunk_bytes(data):
            digest = hashlib.sha256(ch).digest()
            if digest in known:
                wire += TOKEN_BYTES
                ref += 1
            else:
                wire += len(ch) + HEADER_BYTES
                full += 1
                known.add(digest)
    return {"wire_bytes": wire, "multiplier": input_bytes / wire if wire else 0.0, "full_frames": full, "ref_frames": ref}


def gzip_multiplier(root: Path) -> float:
    out = bytearray()
    for rel, data in iter_files(root):
        rb = rel.encode("utf-8")
        out += len(rb).to_bytes(4, "big") + rb + len(data).to_bytes(8, "big") + data
    compressed = gzip.compress(bytes(out), compresslevel=6)
    input_bytes = sum(len(data) for _, data in iter_files(root))
    return input_bytes / len(compressed) if compressed else 0.0


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
            "old_tar": str(old_tar.relative_to(ROOT)),
            "new_tar": str(new_tar.relative_to(ROOT)),
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
            "redulink_object_header_bytes": str(rl["object_header_bytes"]),
            "redulink_reconstruction_ok": str(rl["reconstruction_ok"]),
            "secure_wire_bytes": str(sec["wire_bytes"]),
            "secure_multiplier": f"{sec['multiplier']:.6f}",
            "secure_object_header_bytes": str(sec["object_header_bytes"]),
            "secure_reconstruction_ok": str(sec["reconstruction_ok"]),
            "fixed_object_reuse_wire_bytes": str(reuse["wire_bytes"]),
            "fixed_object_reuse_multiplier": f"{reuse['multiplier']:.6f}",
            "gzip_new_object_stream_multiplier": f"{gz:.6f}",
            "rsync_total_multiplier": "not_measured_for_object_stream",
            "interpretation": "Exact named-object encode/decode from public release files with shared warm state; not raw source-tree tarball transfer and not a production trace.",
        }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=ROOT / "results" / "external_object_workload_suite.csv")
    args = ap.parse_args()
    base = ROOT / "data" / "external_public_corpora"
    pairs = [
        ("click-object-sequence-8.1.7-to-8.1.8", base/"click-8.1.7-to-8.1.8"/"old"/"source.tar.gz", base/"click-8.1.7-to-8.1.8"/"new"/"source.tar.gz"),
        ("redis-object-sequence-7.2.4-to-7.2.5", base/"redis-7.2.4-to-7.2.5"/"old"/"source.tar.gz", base/"redis-7.2.4-to-7.2.5"/"new"/"source.tar.gz"),
        ("nginx-object-sequence-1.25.3-to-1.25.4", base/"nginx-1.25.3-to-1.25.4"/"old"/"source.tar.gz", base/"nginx-1.25.3-to-1.25.4"/"new"/"source.tar.gz"),
    ]
    missing = [str(t) for _, o, n in pairs for t in (o, n) if not t.exists()]
    if missing:
        raise SystemExit(
            "external public corpora not present; run "
            "`python3 benchmarks/fetch_external_public_corpora.py` first. Missing: "
            + ", ".join(missing[:2]) + ("..." if len(missing) > 2 else "")
        )
    rows = [run_pair(*p) for p in pairs]
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    print(out)


if __name__ == "__main__":
    main()
