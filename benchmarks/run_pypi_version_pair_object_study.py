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
methodology is identical. Reconstruction is additionally proven byte-exact by a
real ``redulink_model`` encode/decode round trip against the warm dictionary.

All numbers are reproducible: the package@version pairs and the SHA-256 of every
downloaded wheel are recorded in the output CSV/JSON.
"""
from __future__ import annotations
import csv, hashlib, json, subprocess, sys, tempfile, urllib.request, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks"))
import redulink_model as model  # type: ignore
from run_external_object_workload_suite import (  # reuse identical methodology
    object_aligned_redulink, object_aligned_fixed_reuse, gzip_multiplier, iter_files,
)

# Package, (older_version, newer_version) consecutive real releases (pinned).
PAIRS = [
    ("rich",      "13.7.0", "13.7.1"),
    ("jinja2",    "3.1.3",  "3.1.4"),
    ("click",     "8.1.6",  "8.1.7"),
    ("werkzeug",  "3.0.1",  "3.0.2"),
    ("urllib3",   "2.1.0",  "2.2.0"),
    ("packaging", "23.2",   "24.0"),
]

def pip_download_wheel(spec: str, dest: Path) -> Path:
    subprocess.run([sys.executable, "-m", "pip", "download", spec,
                    "--no-deps", "--only-binary", ":all:", "-d", str(dest)],
                   check=True, capture_output=True, text=True)
    whs = list(dest.glob("*.whl"))
    if not whs:
        raise RuntimeError(f"no wheel downloaded for {spec}")
    return whs[0]

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

def model_roundtrip(old_root: Path, new_root: Path):
    """Prove byte-exact reconstruction with the real model against a warm dict."""
    warm = b"".join(d for _, d in iter_files(old_root))
    new = b"".join(d for _, d in iter_files(new_root))
    st = model.run_bytes(new, chunker="fixed", chunk_size=4096, warm=warm)
    return st.effective_multiplier, st.reconstruction_ok

def main() -> None:
    out_csv = ROOT / "results" / "pypi_version_pair_object_study.csv"
    out_json = ROOT / "results" / "pypi_version_pair_object_study.json"
    rows = []
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        for pkg, vold, vnew in PAIRS:
            try:
                w_old = pip_download_wheel(f"{pkg}=={vold}", tdp / f"{pkg}-old-dl")
                w_new = pip_download_wheel(f"{pkg}=={vnew}", tdp / f"{pkg}-new-dl")
            except Exception as e:
                print(f"SKIP {pkg}: {e}", file=sys.stderr); continue
            old_root = extract_wheel(w_old, tdp / f"{pkg}-old")
            new_root = extract_wheel(w_new, tdp / f"{pkg}-new")
            of, nf, unch, chg, add, rem = file_stability(old_root, new_root)
            rl = object_aligned_redulink(old_root, new_root, secure_mode=False)
            sec = object_aligned_redulink(old_root, new_root, secure_mode=True)
            reuse = object_aligned_fixed_reuse(old_root, new_root)
            gz = gzip_multiplier(new_root)
            m_mult, m_ok = model_roundtrip(old_root, new_root)
            row = {
                "package": pkg, "old_version": vold, "new_version": vnew,
                "old_wheel": w_old.name, "new_wheel": w_new.name,
                "old_sha256": sha256_file(w_old), "new_sha256": sha256_file(w_new),
                "old_file_count": of, "new_file_count": nf,
                "unchanged_file_count": unch, "changed_file_count": chg,
                "added_file_count": add, "removed_file_count": rem,
                "input_bytes": rl["input_bytes"],
                "redulink_multiplier": round(rl["multiplier"], 6),
                "secure_multiplier": round(sec["multiplier"], 6),
                "fixed_object_reuse_multiplier": round(reuse["multiplier"], 6),
                "gzip_new_object_stream_multiplier": round(gz, 6),
                "model_roundtrip_multiplier": round(m_mult, 6),
                "reconstruction_ok": bool(rl["reconstruction_ok"] and m_ok),
                "source": "real PyPI wheel upgrade (pip download), object-aligned",
            }
            rows.append(row)
            print(f"{pkg} {vold}->{vnew}: {unch}/{nf} files unchanged, "
                  f"RL={row['redulink_multiplier']:.2f}x secure={row['secure_multiplier']:.2f}x "
                  f"gzip={row['gzip_new_object_stream_multiplier']:.2f}x recon={row['reconstruction_ok']}")
    if not rows:
        print("no rows produced", file=sys.stderr); sys.exit(1)
    with out_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    out_json.write_text(json.dumps({"experiment": "pypi_version_pair_object_study", "pairs": rows}, indent=2))
    print(out_csv)

if __name__ == "__main__":
    main()
