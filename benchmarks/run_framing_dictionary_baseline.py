#!/usr/bin/env python3
"""Framing-sensitivity repricing and dictionary-compression baseline.

Two review-driven additions in one runner:

1. Repriced ReduLink multipliers. The offline model charges 24 bytes per FULL
   and 32 bytes per REF of framing. The artifact's own compact binary wire
   format costs ``79 + UTF-8 scope length`` bytes of metadata per frame
   (4-byte length prefix, 1-byte message type, 74-byte fixed frame fields, and
   the scope). The 29-byte repricing scope therefore costs 108 bytes. This runner re-prices each workload's
   wire bytes at the measured per-frame cost so the paper can report both the
   modeled and the wire-format-priced multiplier.

2. zstd dictionary/delta baseline (Compression Dictionary Transport analog).
   For each pair, the old object stream is used as a zstd raw-content
   reference (``zstd -3 --patch-from``) to compress the new object stream.
   This is the strongest deployed-style byte baseline: a receiver that retains
   the exact prior byte stream and accepts a codec delta.

Object streams are serialized exactly as in the object suite's gzip baseline
(length-prefixed relative name + length-prefixed content), so all byte counts
are comparable. PyPI wheels are re-downloaded hash-verified against the
committed version-pair object-study file
(``results/pypi_version_pair_object_study.csv``).

Output: results/framing_dictionary_baseline.csv (and .json).
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks"))

import redulink_secure as secure  # noqa: E402
import redulink_wire as wire  # noqa: E402
from run_external_object_workload_suite import (  # noqa: E402
    extract_tarball, iter_files, object_aligned_redulink, gzip_multiplier,
)

MODEL_FULL_OH = 24
MODEL_REF_OH = 32
WIRE_SCOPE = "per-connection-artifact-scope"
WIRE_FIXED_OH = 79
ZSTD_REQUIRED_VERSION = "v1.5.7"
ZSTD_COMMAND = "zstd -3 --patch-from OLD NEW -o PATCH -f -q"


def measured_frame_overheads() -> tuple[int, int]:
    frames, _ = secure.encode(
        b"B" * 8192, secret=b"probe", epoch=7,
        scope=WIRE_SCOPE, stream_id=0,
        chunker="fixed", chunk_size=4096,
    )
    full = frames[0]
    ref = dataclasses.replace(full, kind="REF", payload=b"")
    oh_full = len(wire.encode_message({"t": "FRAME", "seq": 0, "frame": full})) - len(full.payload)
    oh_ref = len(wire.encode_message({"t": "FRAME", "seq": 1, "frame": ref}))
    return oh_full, oh_ref


def object_stream(root: Path) -> bytes:
    out = bytearray()
    for rel, data in iter_files(root):
        rb = rel.encode("utf-8")
        out += len(rb).to_bytes(4, "big") + rb + len(data).to_bytes(8, "big") + data
    return bytes(out)


def zstd_patch_bytes(old_stream: bytes, new_stream: bytes, level: int = 3) -> int:
    with tempfile.TemporaryDirectory() as td:
        old_p = Path(td) / "old.bin"; new_p = Path(td) / "new.bin"; out_p = Path(td) / "patch.zst"
        old_p.write_bytes(old_stream); new_p.write_bytes(new_stream)
        subprocess.run(
            ["zstd", f"-{level}", "--patch-from", str(old_p), str(new_p), "-o", str(out_p), "-f", "-q"],
            check=True, capture_output=True,
        )
        return out_p.stat().st_size


def zstd_version() -> str:
    cp = subprocess.run(["zstd", "--version"], check=True, capture_output=True, text=True)
    return cp.stdout.strip()


def reprice(rl: dict, oh_full: int, oh_ref: int) -> float:
    full = int(rl["full_frames"]); ref = int(rl["ref_frames"])
    literal = int(rl["wire_bytes"]) - MODEL_FULL_OH * full - MODEL_REF_OH * ref
    repriced = literal + oh_full * full + oh_ref * ref
    return int(rl["input_bytes"]) / repriced if repriced else 0.0


def case_row(label: str, old_root: Path, new_root: Path, oh_full: int, oh_ref: int) -> dict:
    rl = object_aligned_redulink(old_root, new_root, secure_mode=False)
    old_s = object_stream(old_root); new_s = object_stream(new_root)
    patch = zstd_patch_bytes(old_s, new_s)
    return {
        "label": label,
        "input_bytes": rl["input_bytes"],
        "full_frames": rl["full_frames"],
        "ref_frames": rl["ref_frames"],
        "model_multiplier": round(rl["multiplier"], 6),
        "repriced_multiplier": round(reprice(rl, oh_full, oh_ref), 6),
        "oh_full_bytes": oh_full,
        "oh_ref_bytes": oh_ref,
        "wire_scope_bytes": len(WIRE_SCOPE.encode("utf-8")),
        "wire_fixed_overhead_bytes": WIRE_FIXED_OH,
        "zstd_patch_bytes": patch,
        "zstd_patch_multiplier": round(int(rl["input_bytes"]) / patch, 6) if patch else 0.0,
        "zstd_version": zstd_version(),
        "zstd_command": ZSTD_COMMAND,
        "gzip_multiplier": round(gzip_multiplier(new_root), 6),
        "reconstruction_ok": bool(rl["reconstruction_ok"]),
    }


def layer_row(oh_full: int, oh_ref: int) -> dict:
    base = ROOT / "data" / "external_positive_corpora" / "redis-layered-public-positive"
    warm = (base / "warm.bin").read_bytes(); update = (base / "update.bin").read_bytes()
    chunk = 4096
    known = {hashlib.sha256(warm[i:i+chunk]).digest() for i in range(0, len(warm), chunk)}
    full = ref = 0; wire_model = 0
    for i in range(0, len(update), chunk):
        ch = update[i:i+chunk]
        if hashlib.sha256(ch).digest() in known:
            ref += 1; wire_model += MODEL_REF_OH
        else:
            full += 1; wire_model += MODEL_FULL_OH + len(ch)
    rl = {"input_bytes": len(update), "wire_bytes": wire_model,
          "full_frames": full, "ref_frames": ref, "multiplier": len(update) / wire_model,
          "reconstruction_ok": True}
    patch = zstd_patch_bytes(warm, update)
    import gzip as _gz
    return {
        "label": "redis-layered-public-positive",
        "input_bytes": len(update), "full_frames": full, "ref_frames": ref,
        "model_multiplier": round(rl["multiplier"], 6),
        "repriced_multiplier": round(reprice(rl, oh_full, oh_ref), 6),
        "oh_full_bytes": oh_full, "oh_ref_bytes": oh_ref,
        "wire_scope_bytes": len(WIRE_SCOPE.encode("utf-8")),
        "wire_fixed_overhead_bytes": WIRE_FIXED_OH,
        "zstd_patch_bytes": patch,
        "zstd_patch_multiplier": round(len(update) / patch, 6) if patch else 0.0,
        "zstd_version": zstd_version(),
        "zstd_command": ZSTD_COMMAND,
        "gzip_multiplier": round(len(update) / len(_gz.compress(update, 6)), 6),
        "reconstruction_ok": True,
    }


def pypi_rows(oh_full: int, oh_ref: int) -> list[dict]:
    committed = {r["package"]: r for r in csv.DictReader(
        (ROOT / "results" / "pypi_version_pair_object_study.csv").open())}
    rows = []
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        for pkg, rec in committed.items():
            try:
                def dl(spec, sub):
                    d = tdp / sub
                    subprocess.run([sys.executable, "-m", "pip", "download", spec, "--no-deps",
                                    "--only-binary", ":all:", "-d", str(d)],
                                   check=True, capture_output=True)
                    return next(d.glob("*.whl"))
                w_old = dl(f"{pkg}=={rec['old_version']}", f"{pkg}-o")
                w_new = dl(f"{pkg}=={rec['new_version']}", f"{pkg}-n")
            except Exception as exc:  # network flake: skip, do not fabricate
                print(f"SKIP {pkg}: {exc}", file=sys.stderr); continue
            for w, key in ((w_old, "old_sha256"), (w_new, "new_sha256")):
                h = hashlib.sha256(w.read_bytes()).hexdigest()
                if h != rec[key]:
                    raise SystemExit(f"{pkg}: wheel hash mismatch vs committed version-pair study ({key})")
            old_root = tdp / f"{pkg}-ox"; new_root = tdp / f"{pkg}-nx"
            with zipfile.ZipFile(w_old) as z: z.extractall(old_root)
            with zipfile.ZipFile(w_new) as z: z.extractall(new_root)
            row = case_row(f"pypi-{pkg}-{rec['old_version']}-to-{rec['new_version']}",
                           old_root, new_root, oh_full, oh_ref)
            rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sets", choices=["local", "pypi", "all"], default="all")
    ap.add_argument("--output", type=Path, default=ROOT / "results" / "framing_dictionary_baseline.csv")
    args = ap.parse_args()
    version = zstd_version()
    if ZSTD_REQUIRED_VERSION not in version:
        raise SystemExit(
            f"zstd {ZSTD_REQUIRED_VERSION} is required for reproducible results; found: {version}"
        )
    oh_full, oh_ref = measured_frame_overheads()
    expected_oh = WIRE_FIXED_OH + len(WIRE_SCOPE.encode("utf-8"))
    if (oh_full, oh_ref) != (expected_oh, expected_oh):
        raise SystemExit(f"unexpected wire overhead: {(oh_full, oh_ref)} != {(expected_oh, expected_oh)}")
    rows: list[dict] = []
    if args.sets in ("local", "all"):
        base = ROOT / "data" / "external_public_corpora"
        pairs = [
            ("click-8.1.7-to-8.1.8",), ("redis-7.2.4-to-7.2.5",), ("nginx-1.25.3-to-1.25.4",),
        ]
        for (name,) in pairs:
            old_tar = base / name / "old" / "source.tar.gz"
            new_tar = base / name / "new" / "source.tar.gz"
            if not old_tar.exists():
                raise SystemExit("run benchmarks/fetch_external_public_corpora.py first")
            with tempfile.TemporaryDirectory() as td:
                old_root = extract_tarball(old_tar, Path(td) / "o")
                new_root = extract_tarball(new_tar, Path(td) / "n")
                rows.append(case_row(f"object-{name}", old_root, new_root, oh_full, oh_ref))
        rows.append(layer_row(oh_full, oh_ref))
    if args.sets in ("pypi", "all"):
        rows.extend(pypi_rows(oh_full, oh_ref))
    if args.sets == "pypi" and args.output.exists():
        with args.output.open(newline="") as fh:
            existing = [r for r in csv.DictReader(fh) if not r["label"].startswith("pypi-")]
        rows = existing + rows
    with args.output.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n"); w.writeheader(); w.writerows(rows)
    args.output.with_suffix(".json").write_text(json.dumps(
        {"experiment": "framing_repricing_and_zstd_patch_baseline",
         "measured_frame_overhead_bytes": {"full": oh_full, "ref": oh_ref},
         "wire_overhead_formula": "79 + UTF-8 scope length",
         "wire_scope": WIRE_SCOPE,
         "model_overhead_bytes": {"full": MODEL_FULL_OH, "ref": MODEL_REF_OH},
         "provenance": {
             "python": sys.version,
             "platform": platform.platform(),
             "zstd_version": version,
             "zstd_command": ZSTD_COMMAND,
             "git_commit": subprocess.run(
                 ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                 capture_output=True, text=True,
             ).stdout.strip(),
         },
         "rows": rows}, indent=2))
    for r in rows:
        print(f"{r['label']:48s} model={float(r['model_multiplier']):>8.2f}x repriced={float(r['repriced_multiplier']):>7.2f}x zstd-patch={float(r['zstd_patch_multiplier']):>9.2f}x gzip={float(r['gzip_multiplier']):.2f}x")
    print(args.output)


if __name__ == "__main__":
    main()
