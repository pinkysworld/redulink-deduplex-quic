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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_secure as secure  # type: ignore
import redulink_wire as wire  # type: ignore

RAW_STREAM_SCOPE = "raw-stream-artifact-v1"
RAW_STREAM_SECRET = hashlib.sha256(b"ReduLink public raw-stream artifact test key v1").digest()
RAW_STREAM_DICTIONARY_BUDGET = 8192


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


def canonical_binary_redulink(old: bytes, new: bytes, *, chunk_size: int) -> dict[str, object]:
    """Serialize the complete no-miss application-stream profile and decode it."""
    frames, stats = secure.encode(
        new,
        warm_dictionary=old,
        secret=RAW_STREAM_SECRET,
        epoch=1,
        scope=RAW_STREAM_SCOPE,
        stream_id=0,
        chunker="fixed",
        chunk_size=chunk_size,
        max_dict_chunks=RAW_STREAM_DICTIONARY_BUDGET,
    )
    messages = [wire.encode_message({
        "t": "HELLO",
        "version": 1,
        "chunk_size": chunk_size,
        "frame_count": len(frames),
        "input_length": len(new),
        "input_sha256": hashlib.sha256(new).hexdigest(),
    })]
    messages.extend(
        wire.encode_message({"t": "FRAME", "seq": seq, "frame": frame})
        for seq, frame in enumerate(frames)
    )
    messages.extend([
        wire.encode_message({"t": "END_ROUND"}),
        wire.encode_message({"t": "MISSING", "items": []}),
        wire.encode_message({"t": "FINISH"}),
    ])
    decoded = []
    for message in messages:
        body_length = int.from_bytes(message[:wire.LEN_BYTES], "big")
        if body_length != len(message) - wire.LEN_BYTES:
            raise ValueError("binary profile length prefix mismatch")
        decoded.append(wire.decode_payload(message[wire.LEN_BYTES:]))
    expected_types = (
        ["HELLO"] + ["FRAME"] * len(frames)
        + ["END_ROUND", "MISSING", "FINISH"]
    )
    decoded_types = [message.t for message in decoded]
    decoded_hello = decoded[0].obj
    wire_decode_ok = (
        decoded_types == expected_types
        and int(decoded_hello["input_length"]) == len(new)
        and str(decoded_hello["input_sha256"]) == hashlib.sha256(new).hexdigest()
        and list(decoded[-2].obj["items"]) == []
    )
    decoded_frames = [message.obj["frame"] for message in decoded if message.t == "FRAME"]
    reconstructed = secure.decode(
        decoded_frames,
        warm_dictionary=old,
        secret=RAW_STREAM_SECRET,
        epoch=1,
        scope=RAW_STREAM_SCOPE,
        stream_id=0,
        chunker="fixed",
        chunk_size=chunk_size,
        max_dict_chunks=RAW_STREAM_DICTIONARY_BUDGET,
        max_reconstructed_bytes=max(len(new), 1),
    ) if decoded_frames else b""
    wire_bytes = sum(len(message) for message in messages)
    return {
        "wire_bytes": wire_bytes,
        "multiplier": len(new) / wire_bytes if wire_bytes else 0.0,
        "full_frames": stats.full_frames,
        "ref_frames": stats.ref_frames,
        "wire_decode_ok": wire_decode_ok,
        "reconstruction_ok": wire_decode_ok and reconstructed == new,
    }


def run_one(row: dict[str, str]) -> dict[str, str]:
    label = row.get("label") or row.get("workload") or "workload"
    old_path = Path(row["old_path"])
    new_path = Path(row["new_path"])
    chunker = row.get("chunker", "fixed") or "fixed"
    chunk_size = int(row.get("chunk_size", "4096") or 4096)
    if chunker != "fixed":
        raise ValueError("the canonical binary evidence runner requires fixed chunking")
    old = read_bytes(old_path)
    new = read_bytes(new_path)
    binary = canonical_binary_redulink(old, new, chunk_size=chunk_size)
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
        "binary_profile_wire_bytes": str(binary["wire_bytes"]),
        "binary_profile_multiplier": f"{float(binary['multiplier']):.6f}",
        "binary_profile_full_frames": str(binary["full_frames"]),
        "binary_profile_ref_frames": str(binary["ref_frames"]),
        "binary_profile_wire_decode_ok": str(binary["wire_decode_ok"]),
        "binary_profile_reconstruction_ok": str(binary["reconstruction_ok"]),
        "dictionary_budget_chunks": str(RAW_STREAM_DICTIONARY_BUDGET),
        "authentication_key_provenance": "public deterministic artifact test key; byte serialization and exactness only",
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
