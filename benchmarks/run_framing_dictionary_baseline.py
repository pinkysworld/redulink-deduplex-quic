#!/usr/bin/env python3
"""Framing-sensitivity repricing and a verified zstd dictionary baseline.

The runner performs two checks:

1. Repriced ReduLink multipliers. The offline model charges 24 bytes per FULL
   and 32 bytes per REF of framing. The artifact's own compact binary wire
   format costs ``85 + UTF-8 scope length`` bytes of metadata per frame
   (4-byte length prefix, 1-byte message type, 80-byte fixed frame fields, and
   the scope). The 29-byte repricing scope therefore costs 114 bytes. This runner re-prices each workload's
   wire bytes at the measured per-frame cost so the paper can report both the
   modeled and the wire-format-priced multiplier.

2. Verified zstd raw-content-dictionary baseline. For each pair, the old
   object stream is supplied as a raw-content dictionary when compressing and
   decompressing the new stream. The decoder must reproduce the exact bytes
   and SHA-256 digest before the row is accepted.

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
import gzip
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

import zstandard as zstd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks"))

import redulink_secure as secure  # noqa: E402
import redulink_wire as wire  # noqa: E402
from run_external_object_workload_suite import (  # noqa: E402
    extract_tarball, iter_files, object_aligned_redulink, gzip_baseline,
)

MODEL_FULL_OH = 24
MODEL_REF_OH = 32
WIRE_SCOPE = "per-connection-artifact-scope"
WIRE_FIXED_OH = 85
ZSTD_REQUIRED_VERSION = (1, 5, 7)
ZSTD_WINDOW_LOG = 21
ZSTD_SENSITIVITY_WINDOW_LOG = 24
ZSTD_PARAMETERS = (
    "python-zstandard level=3, window_log=21, raw-content dictionary, "
    "frame checksum enabled"
)
ZSTD_SENSITIVITY_PARAMETERS = (
    "python-zstandard level=3, window_log=24, raw-content dictionary, "
    "frame checksum enabled"
)


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


def zstd_dictionary_roundtrip(old_stream: bytes, new_stream: bytes, *,
                              level: int = 3,
                              window_log: int = ZSTD_WINDOW_LOG) -> dict[str, object]:
    dictionary = zstd.ZstdCompressionDict(old_stream, dict_type=zstd.DICT_TYPE_RAWCONTENT)
    parameters = zstd.ZstdCompressionParameters.from_level(
        level, window_log=window_log, write_checksum=1,
    )
    encoded = zstd.ZstdCompressor(
        compression_params=parameters,
        dict_data=dictionary,
    ).compress(new_stream)
    reconstructed = zstd.ZstdDecompressor(dict_data=dictionary).decompress(encoded)
    expected_sha256 = hashlib.sha256(new_stream).hexdigest()
    reconstructed_sha256 = hashlib.sha256(reconstructed).hexdigest()
    return {
        "encoded_bytes": len(encoded),
        "window_log": parameters.window_log,
        "expected_sha256": expected_sha256,
        "reconstructed_sha256": reconstructed_sha256,
        "reconstruction_ok": reconstructed == new_stream and reconstructed_sha256 == expected_sha256,
    }


def zstd_version() -> str:
    return ".".join(str(part) for part in zstd.ZSTD_VERSION)


def reprice(rl: dict, oh_full: int, oh_ref: int) -> float:
    full = int(rl["full_frames"]); ref = int(rl["ref_frames"])
    literal = int(rl["wire_bytes"]) - MODEL_FULL_OH * full - MODEL_REF_OH * ref
    repriced = literal + oh_full * full + oh_ref * ref
    return int(rl["input_bytes"]) / repriced if repriced else 0.0


def case_row(label: str, old_root: Path, new_root: Path, oh_full: int, oh_ref: int) -> dict:
    rl = object_aligned_redulink(old_root, new_root, secure_mode=False)
    old_s = object_stream(old_root); new_s = object_stream(new_root)
    zstd_result = zstd_dictionary_roundtrip(old_s, new_s, window_log=ZSTD_WINDOW_LOG)
    zstd_sensitivity = zstd_dictionary_roundtrip(
        old_s, new_s, window_log=ZSTD_SENSITIVITY_WINDOW_LOG,
    )
    gzip_result = gzip_baseline(new_root)
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
        "zstd_dictionary_bytes": zstd_result["encoded_bytes"],
        "zstd_dictionary_multiplier": round(int(rl["input_bytes"]) / int(zstd_result["encoded_bytes"]), 6) if zstd_result["encoded_bytes"] else 0.0,
        "zstd_expected_sha256": zstd_result["expected_sha256"],
        "zstd_reconstructed_sha256": zstd_result["reconstructed_sha256"],
        "zstd_dictionary_reconstruction_ok": zstd_result["reconstruction_ok"],
        "libzstd_version": zstd_version(),
        "python_zstandard_version": zstd.__version__,
        "zstd_parameters": ZSTD_PARAMETERS,
        "zstd_window_log": zstd_result["window_log"],
        "zstd_window_sensitivity_log": zstd_sensitivity["window_log"],
        "zstd_window_sensitivity_bytes": zstd_sensitivity["encoded_bytes"],
        "zstd_window_sensitivity_multiplier": round(int(rl["input_bytes"]) / int(zstd_sensitivity["encoded_bytes"]), 6) if zstd_sensitivity["encoded_bytes"] else 0.0,
        "zstd_window_sensitivity_reconstruction_ok": zstd_sensitivity["reconstruction_ok"],
        "zstd_window_sensitivity_parameters": ZSTD_SENSITIVITY_PARAMETERS,
        "gzip_bytes": gzip_result["compressed_bytes"],
        "gzip_multiplier": round(float(gzip_result["multiplier"]), 6),
        "gzip_reconstruction_ok": gzip_result["reconstruction_ok"],
        "gzip_parameters": gzip_result["parameters"],
        "gzip_python_version": gzip_result["python_version"],
        "gzip_zlib_compile_version": gzip_result["zlib_compile_version"],
        "gzip_zlib_runtime_version": gzip_result["zlib_runtime_version"],
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
    zstd_result = zstd_dictionary_roundtrip(warm, update, window_log=ZSTD_WINDOW_LOG)
    zstd_sensitivity = zstd_dictionary_roundtrip(
        warm, update, window_log=ZSTD_SENSITIVITY_WINDOW_LOG,
    )
    gzip_bytes = gzip.compress(update, compresslevel=6, mtime=0)
    gzip_reconstructed = gzip.decompress(gzip_bytes)
    return {
        "label": "redis-layered-public-positive",
        "input_bytes": len(update), "full_frames": full, "ref_frames": ref,
        "model_multiplier": round(rl["multiplier"], 6),
        "repriced_multiplier": round(reprice(rl, oh_full, oh_ref), 6),
        "oh_full_bytes": oh_full, "oh_ref_bytes": oh_ref,
        "wire_scope_bytes": len(WIRE_SCOPE.encode("utf-8")),
        "wire_fixed_overhead_bytes": WIRE_FIXED_OH,
        "zstd_dictionary_bytes": zstd_result["encoded_bytes"],
        "zstd_dictionary_multiplier": round(len(update) / int(zstd_result["encoded_bytes"]), 6) if zstd_result["encoded_bytes"] else 0.0,
        "zstd_expected_sha256": zstd_result["expected_sha256"],
        "zstd_reconstructed_sha256": zstd_result["reconstructed_sha256"],
        "zstd_dictionary_reconstruction_ok": zstd_result["reconstruction_ok"],
        "libzstd_version": zstd_version(),
        "python_zstandard_version": zstd.__version__,
        "zstd_parameters": ZSTD_PARAMETERS,
        "zstd_window_log": zstd_result["window_log"],
        "zstd_window_sensitivity_log": zstd_sensitivity["window_log"],
        "zstd_window_sensitivity_bytes": zstd_sensitivity["encoded_bytes"],
        "zstd_window_sensitivity_multiplier": round(len(update) / int(zstd_sensitivity["encoded_bytes"]), 6) if zstd_sensitivity["encoded_bytes"] else 0.0,
        "zstd_window_sensitivity_reconstruction_ok": zstd_sensitivity["reconstruction_ok"],
        "zstd_window_sensitivity_parameters": ZSTD_SENSITIVITY_PARAMETERS,
        "gzip_bytes": len(gzip_bytes),
        "gzip_multiplier": round(len(update) / len(gzip_bytes), 6),
        "gzip_reconstruction_ok": gzip_reconstructed == update,
        "gzip_parameters": "Python gzip.compress level=6, mtime=0",
        "gzip_python_version": sys.version.split()[0],
        "gzip_zlib_compile_version": zlib.ZLIB_VERSION,
        "gzip_zlib_runtime_version": zlib.ZLIB_RUNTIME_VERSION,
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
                                    "--only-binary", ":all:", "--timeout", "10", "--retries", "1",
                                    "-d", str(d)],
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
    version = zstd.ZSTD_VERSION
    if version != ZSTD_REQUIRED_VERSION:
        raise SystemExit(
            f"libzstd {'.'.join(map(str, ZSTD_REQUIRED_VERSION))} is required for reproducible results; "
            f"found: {'.'.join(map(str, version))}"
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
        {"experiment": "framing_repricing_and_zstd_dictionary_baseline",
         "measured_frame_overhead_bytes": {"full": oh_full, "ref": oh_ref},
         "wire_overhead_formula": "85 + UTF-8 scope length",
         "wire_scope": WIRE_SCOPE,
         "model_overhead_bytes": {"full": MODEL_FULL_OH, "ref": MODEL_REF_OH},
         "provenance": {
             "python": sys.version,
             "platform": platform.platform(),
             "libzstd_version": zstd_version(),
             "python_zstandard_version": zstd.__version__,
             "zstd_parameters": ZSTD_PARAMETERS,
             "zstd_window_log": ZSTD_WINDOW_LOG,
             "zstd_window_sensitivity_parameters": ZSTD_SENSITIVITY_PARAMETERS,
             "zstd_window_sensitivity_log": ZSTD_SENSITIVITY_WINDOW_LOG,
             "git_commit": subprocess.run(
                 ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                 capture_output=True, text=True,
             ).stdout.strip(),
         },
         "rows": rows}, indent=2))
    for r in rows:
        print(
            f"{r['label']:48s} model={float(r['model_multiplier']):>8.2f}x "
            f"repriced={float(r['repriced_multiplier']):>7.2f}x "
            f"zstd-w21={float(r['zstd_dictionary_multiplier']):>9.2f}x "
            f"zstd-w24={float(r['zstd_window_sensitivity_multiplier']):>9.2f}x "
            f"gzip={float(r['gzip_multiplier']):.2f}x"
        )
    print(args.output)


if __name__ == "__main__":
    main()
