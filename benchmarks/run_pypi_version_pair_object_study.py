#!/usr/bin/env python3
"""Independent PyPI version-pair object study.

This runner does NOT construct or synthesize repeated bytes. It downloads real,
hash-pinned wheel distributions for consecutive released versions of widely used
Python packages directly from PyPI (via ``pip download``), then measures how much
of the newer release is byte-identical to the older one a client already holds.

It models the package-registry / CDN object-delivery use case: a client that has
already installed version N upgrades to version N+1, retaining a warm same-origin
dictionary. Each distribution member (file inside the wheel) is treated as an
individually framed object, exactly as in ``run_external_object_workload_suite``;
the same object-aligned accounting functions are imported from that module so the
methodology is identical. Reconstruction is proven byte-exact for the complete
ordered mapping of object names (including empty objects) to object contents in
both the plain and authenticated profiles.

All numbers are reproducible: the package@version pairs and the SHA-256 of every
downloaded wheel are recorded in the output CSV/JSON.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks"))
from run_external_object_workload_suite import (  # reuse identical methodology
    object_aligned_redulink, object_aligned_chunk_token_reuse, whole_object_cas,
    gzip_baseline, iter_files,
)

# Package, (older_version, newer_version) consecutive real releases (pinned).
PAIRS = [
    ("rich",      "13.7.0", "13.7.1"),
    ("jinja2",    "3.1.3",  "3.1.4"),
    ("click",     "8.1.6",  "8.1.7"),
    ("werkzeug",  "3.0.1",  "3.0.2"),
]

EXPECTED_WHEEL_SHA256 = {
    ("rich", "13.7.0"): "6da14c108c4866ee9520bbffa71f6fe3962e193b7da68720583850cd4548e235",
    ("rich", "13.7.1"): "4edbae314f59eb482f54e9e30bf00d33350aaa94f4bfcd4e9e3110e64d0d7222",
    ("jinja2", "3.1.3"): "7d6d50dd97d52cbc355597bd845fabfbac3f551e1f99619e39a35ce8c370b5fa",
    ("jinja2", "3.1.4"): "bc5dd2abb727a5319567b7a813e6a2e7318c39f4f487cfe6c89c6f9c7d25197d",
    ("click", "8.1.6"): "fa244bb30b3b5ee2cae3da8f55c9e5e0c0e86093306301fb418eb9dc40fbded5",
    ("click", "8.1.7"): "ae74fb96c20a0277a1d615f1e4d73c8414f5a98db8b799a7931d1582f3390c28",
    ("werkzeug", "3.0.1"): "90a285dc0e42ad56b34e696398b8122ee4c681833fb35b8334a095d82c56da10",
    ("werkzeug", "3.0.2"): "3aac3f5da756f93030740bc235d3e09449efcf65f2f55e3602e1d851b8f48795",
}

def pip_download_wheel(spec: str, dest: Path) -> Path:
    subprocess.run([sys.executable, "-m", "pip", "download", spec,
                    "--no-deps", "--only-binary", ":all:", "--timeout", "10",
                    "--retries", "1", "-d", str(dest)],
                   check=True, capture_output=True, text=True)
    whs = list(dest.glob("*.whl"))
    if not whs:
        raise RuntimeError(f"no wheel downloaded for {spec}")
    return whs[0]

def cached_wheel(cache: Path, package: str, version: str) -> Path:
    prefix = f"{package.lower().replace('_', '-')}-{version}-"
    candidates = [
        path for path in cache.rglob("*.whl")
        if path.name.lower().replace("_", "-").startswith(prefix)
    ]
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"expected one cached wheel for {package}=={version}, found {len(candidates)}"
        )
    return candidates[0]

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def extract_wheel(wheel: Path, dest: Path) -> Path:
    with zipfile.ZipFile(wheel) as z:
        z.extractall(dest)
    return dest

def file_stability(old_root: Path, new_root: Path):
    oldf = {rel: hashlib.sha256(d).hexdigest() for rel, d in iter_files(old_root)}
    newf = {rel: hashlib.sha256(d).hexdigest() for rel, d in iter_files(new_root)}
    unchanged = sum(1 for r, h in newf.items() if r in oldf and oldf[r] == h)
    changed = sum(1 for r, h in newf.items() if r in oldf and oldf[r] != h)
    added = sum(1 for r in newf if r not in oldf)
    removed = sum(1 for r in oldf if r not in newf)
    return len(oldf), len(newf), unchanged, changed, added, removed

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-cache", type=Path, default=None,
                        help="optional directory containing previously downloaded wheels")
    parser.add_argument(
        "--allow-partial", action="store_true",
        help="continue after an unavailable pair; disabled by default for submission evidence",
    )
    parser.add_argument("--output-csv", type=Path, default=ROOT / "results" / "pypi_version_pair_object_study.csv")
    parser.add_argument("--output-json", type=Path, default=ROOT / "results" / "pypi_version_pair_object_study.json")
    args = parser.parse_args()
    rows = []
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        for pkg, vold, vnew in PAIRS:
            try:
                if args.wheel_cache is not None:
                    w_old = cached_wheel(args.wheel_cache, pkg, vold)
                    w_new = cached_wheel(args.wheel_cache, pkg, vnew)
                else:
                    w_old = pip_download_wheel(f"{pkg}=={vold}", tdp / f"{pkg}-old-dl")
                    w_new = pip_download_wheel(f"{pkg}=={vnew}", tdp / f"{pkg}-new-dl")
            except Exception as e:
                if not args.allow_partial:
                    raise RuntimeError(f"required pair unavailable: {pkg} {vold}->{vnew}") from e
                print(f"SKIP {pkg}: {e}", file=sys.stderr)
                continue
            old_hash = sha256_file(w_old)
            new_hash = sha256_file(w_new)
            if old_hash != EXPECTED_WHEEL_SHA256[(pkg, vold)]:
                raise ValueError(f"SHA-256 mismatch for {pkg}=={vold}")
            if new_hash != EXPECTED_WHEEL_SHA256[(pkg, vnew)]:
                raise ValueError(f"SHA-256 mismatch for {pkg}=={vnew}")
            old_root = extract_wheel(w_old, tdp / f"{pkg}-old")
            new_root = extract_wheel(w_new, tdp / f"{pkg}-new")
            of, nf, unch, chg, add, rem = file_stability(old_root, new_root)
            rl = object_aligned_redulink(old_root, new_root, secure_mode=False)
            sec = object_aligned_redulink(old_root, new_root, secure_mode=True)
            chunk_reuse = object_aligned_chunk_token_reuse(old_root, new_root)
            object_cas = whole_object_cas(old_root, new_root)
            gz = gzip_baseline(new_root)
            row = {
                "package": pkg, "old_version": vold, "new_version": vnew,
                "old_wheel": w_old.name, "new_wheel": w_new.name,
                "old_sha256": old_hash, "new_sha256": new_hash,
                "old_file_count": of, "new_file_count": nf,
                "unchanged_file_count": unch, "changed_file_count": chg,
                "added_file_count": add, "removed_file_count": rem,
                "input_bytes": rl["input_bytes"],
                "redulink_wire_bytes": rl["wire_bytes"],
                "redulink_multiplier": round(rl["multiplier"], 6),
                "secure_wire_bytes": sec["wire_bytes"],
                "secure_multiplier": round(sec["multiplier"], 6),
                "dictionary_budget_chunks": sec["dictionary_budget_chunks"],
                "secure_wire_serialization_ok": bool(sec["wire_serialization_ok"]),
                "secure_object_header_serialization_ok": bool(sec["object_header_serialization_ok"]),
                "secure_authentication_key_provenance": sec["authentication_key_provenance"],
                "chunk_token_reuse_bytes": chunk_reuse["wire_bytes"],
                "chunk_token_reuse_multiplier": round(chunk_reuse["multiplier"], 6),
                "chunk_token_reuse_reconstruction_ok": bool(chunk_reuse["reconstruction_ok"]),
                "whole_object_cas_bytes": object_cas["wire_bytes"],
                "whole_object_cas_multiplier": round(object_cas["multiplier"], 6),
                "whole_object_cas_reconstruction_ok": bool(object_cas["reconstruction_ok"]),
                "gzip_new_object_stream_bytes": gz["compressed_bytes"],
                "gzip_new_object_stream_multiplier": round(float(gz["multiplier"]), 6),
                "gzip_reconstruction_ok": bool(gz["reconstruction_ok"]),
                "gzip_parameters": gz["parameters"],
                "gzip_python_version": gz["python_version"],
                "gzip_zlib_compile_version": gz["zlib_compile_version"],
                "gzip_zlib_runtime_version": gz["zlib_runtime_version"],
                "object_roundtrip_multiplier": round(rl["multiplier"], 6),
                "reconstruction_ok": bool(rl["reconstruction_ok"] and sec["reconstruction_ok"]),
                "source": "hash-pinned PyPI wheel upgrade, object-aligned",
            }
            rows.append(row)
            print(f"{pkg} {vold}->{vnew}: {unch}/{nf} files unchanged, "
                  f"RL={row['redulink_multiplier']:.2f}x secure={row['secure_multiplier']:.2f}x "
                  f"gzip={row['gzip_new_object_stream_multiplier']:.2f}x recon={row['reconstruction_ok']}")
    if not rows:
        print("no rows produced", file=sys.stderr); sys.exit(1)
    if not args.allow_partial and len(rows) != len(PAIRS):
        raise RuntimeError(f"expected {len(PAIRS)} required pairs, produced {len(rows)}")
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n"); w.writeheader(); w.writerows(rows)
    args.output_json.write_text(json.dumps({"experiment": "pypi_version_pair_object_study", "pairs": rows}, indent=2))
    print(args.output_csv)

if __name__ == "__main__":
    main()
