#!/usr/bin/env python3
"""Generate raw/compression/ReduLink baseline comparison CSVs."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_proto_v0_5 as redulink


HEADER = [
    "family",
    "artifact",
    "mode",
    "chunker",
    "method",
    "input_bytes",
    "wire_bytes",
    "saving_rate",
    "effective_multiplier",
    "chunks",
    "full_frames",
    "ref_frames",
    "reconstruction_ok",
    "comparable",
    "notes",
]


def gzip_bytes(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=6, mtime=0)


def zstd_bytes(data: bytes) -> bytes | None:
    zstd = shutil.which("zstd")
    if zstd is None:
        return None
    proc = subprocess.run(
        [zstd, "-q", "-c", "-3"],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return proc.stdout


def rsync_block_reuse(update: bytes, warm: bytes, block_size: int) -> tuple[int, int, int]:
    """Return modeled rsync-like wire bytes, literal runs, and matched blocks.

    The receiver exposes fixed-block signatures for the warm artifact. The
    sender scans the update byte stream and emits a reference when an old block
    appears at any offset; otherwise it coalesces unmatched bytes into literal
    runs. This approximates rsync's offset-resynchronizing behavior without
    implementing its exact rolling checksum protocol.
    """
    literal_run_overhead = 20
    token_overhead = 16
    prefix = min(16, block_size)
    warm_blocks: dict[bytes, list[bytes]] = {}
    for i in range(0, len(warm), block_size):
        block = warm[i:i + block_size]
        if len(block) == block_size:
            warm_blocks.setdefault(block[:prefix], []).append(block)

    wire = 0
    literal_runs = 0
    matched = 0

    pos = 0
    literal_len = 0
    while pos < len(update):
        found = False
        if pos + block_size <= len(update):
            candidates = warm_blocks.get(update[pos:pos + prefix], [])
            for block in candidates:
                if update[pos:pos + block_size] == block:
                    if literal_len:
                        wire += literal_run_overhead + literal_len
                        literal_runs += 1
                        literal_len = 0
                    wire += token_overhead
                    matched += 1
                    pos += block_size
                    found = True
                    break
        if found:
            continue
        literal_len += 1
        pos += 1

    if literal_len:
        wire += literal_run_overhead + literal_len
        literal_runs += 1

    return wire, literal_runs, matched


def write_metadata(output: Path) -> None:
    zstd = shutil.which("zstd")
    metadata = {
        "python": sys.version.split()[0],
        "gzip_module": "python-stdlib",
        "zstd_path": zstd or "",
        "zstd_version": "",
    }
    if zstd:
        proc = subprocess.run([zstd, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        metadata["zstd_version"] = proc.stdout.strip()
    output.with_suffix(output.suffix + ".metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


def synthetic_base() -> bytes:
    return b"".join(
        f"INFO service=api tenant={i % 64} status=200 template=login latency={i % 101}\n".encode()
        for i in range(40000)
    )


def synthetic_data(variant: str) -> bytes:
    base = synthetic_base()
    if variant == "logs":
        return base + b"new log shard\n" * 2000
    if variant == "updates":
        return base[: len(base) // 2] + b"release metadata changed\n" * 1000 + base[len(base) // 2:]
    if variant == "mixed":
        return base + bytes((i * 131) % 251 for i in range(len(base) // 4))
    raise ValueError(f"unknown synthetic variant: {variant}")


def synthetic_warm_update(variant: str) -> tuple[bytes, bytes]:
    base = b"".join(
        f"INFO service=api tenant={i % 64} status=200 template=login latency={i % 101}\n".encode()
        for i in range(40000)
    )
    if variant == "logs":
        return base, base + b"new log shard\n" * 2000
    if variant == "updates":
        update = base[: len(base) // 2] + b"release metadata changed\n" * 1000 + base[len(base) // 2:]
        return base, update
    if variant == "mixed":
        return base, base + bytes((i * 131) % 251 for i in range(len(base) // 4))
    raise ValueError(f"unknown synthetic variant: {variant}")


def split_warm(data: bytes, warm_fraction: float) -> tuple[bytes, bytes]:
    cut = max(1, min(len(data) - 1, int(len(data) * warm_fraction)))
    return data[:cut], data[cut:]


def metric_row(family: str, artifact: str, mode: str, chunker: str, method: str,
               input_len: int, wire_len: int, notes: str = "",
               chunks: int = 0, full: int = 0, ref: int = 0,
               ok: bool = True, comparable: bool = True) -> dict[str, str]:
    saving = max(0.0, 1.0 - (wire_len / input_len)) if input_len else 0.0
    multiplier = (input_len / wire_len) if wire_len else 1.0
    return {
        "family": family,
        "artifact": artifact,
        "mode": mode,
        "chunker": chunker,
        "method": method,
        "input_bytes": str(input_len),
        "wire_bytes": str(wire_len),
        "saving_rate": f"{saving:.6f}",
        "effective_multiplier": f"{multiplier:.6f}",
        "chunks": str(chunks),
        "full_frames": str(full),
        "ref_frames": str(ref),
        "reconstruction_ok": str(ok),
        "comparable": str(comparable),
        "notes": notes,
    }


def stats_row(family: str, artifact: str, mode: str, chunker: str, method: str,
              stats: redulink.Stats, notes: str = "", comparable: bool = True) -> dict[str, str]:
    return {
        "family": family,
        "artifact": artifact,
        "mode": mode,
        "chunker": chunker,
        "method": method,
        "input_bytes": str(stats.input_bytes),
        "wire_bytes": str(stats.wire_bytes),
        "saving_rate": f"{stats.saving_rate:.6f}",
        "effective_multiplier": f"{stats.effective_multiplier:.6f}",
        "chunks": str(stats.chunks),
        "full_frames": str(stats.full_frames),
        "ref_frames": str(stats.ref_frames),
        "reconstruction_ok": str(stats.reconstruction_ok),
        "comparable": str(comparable),
        "notes": notes,
    }


def frame_stream_bytes(frames: list[redulink.Frame]) -> bytes:
    out = io.BytesIO()
    for fr in frames:
        if fr.kind == "FULL":
            out.write(b"F ")
            out.write(fr.cid.encode("ascii"))
            out.write(f" {fr.length}\n".encode("ascii"))
            out.write(fr.payload)
            out.write(b"\n")
        elif fr.kind == "REF":
            out.write(b"R ")
            out.write(fr.cid.encode("ascii"))
            out.write(f" {fr.length}\n".encode("ascii"))
        else:
            raise ValueError(f"unknown frame kind: {fr.kind}")
    return out.getvalue()


def evaluate_artifact(family: str, artifact: str, data: bytes, *,
                      chunk_size: int, warm_fraction: float,
                      warm_update: tuple[bytes, bytes] | None = None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    rows.append(metric_row(family, artifact, "single-object", "none", "raw", len(data), len(data)))

    gz = gzip_bytes(data)
    rows.append(metric_row(family, artifact, "single-object", "none", "gzip-6", len(data), len(gz)))

    zstd = zstd_bytes(data)
    if zstd is not None:
        rows.append(metric_row(family, artifact, "single-object", "none", "zstd-3", len(data), len(zstd)))
    else:
        rows.append(metric_row(family, artifact, "single-object", "none", "zstd-3", len(data), len(data),
                               ok=False, notes="zstd command unavailable; row records raw byte count placeholder"))

    if warm_update is None:
        warm, update = split_warm(data, warm_fraction)
    else:
        warm, update = warm_update

    rsync_wire, rsync_full, rsync_ref = rsync_block_reuse(update, warm, chunk_size)
    rows.append(metric_row(
        family,
        artifact,
        "warm-update-like",
        "fixed",
        "rsync-block-reuse",
        len(update),
        rsync_wire,
        chunks=rsync_full + rsync_ref,
        full=rsync_full,
        ref=rsync_ref,
        notes="fixed-block rsync-style reuse baseline against warm artifact",
    ))

    for chunker in ("fixed", "cdc"):
        cold = redulink.run_bytes(data, chunker=chunker, chunk_size=chunk_size)
        rows.append(stats_row(family, artifact, "cold-intra-artifact", chunker, "redulink", cold))

        warm_stats = redulink.run_bytes(update, chunker=chunker, chunk_size=chunk_size, warm=warm)
        rows.append(stats_row(family, artifact, "warm-update-like", chunker, "redulink", warm_stats))

    gz_warm = gzip_bytes(warm)
    gz_update = gzip_bytes(update)
    gz_then_rl = redulink.run_bytes(gz_update, chunker="cdc", chunk_size=chunk_size, warm=gz_warm)
    rows.append(stats_row(family, artifact, "warm-update-like", "cdc", "gzip-then-redulink", gz_then_rl,
                          notes="ReduLink applied after gzip compression"))

    frames, rl_stats = redulink.encode(update, chunker="cdc", chunk_size=chunk_size, warm_dictionary=warm)
    reconstructed = redulink.decode(frames, chunker="cdc", chunk_size=chunk_size, warm_dictionary=warm)
    compressed_frame_stream = gzip_bytes(frame_stream_bytes(frames))
    rows.append(metric_row(
        family,
        artifact,
        "warm-update-like",
        "cdc",
        "redulink-then-gzip",
        len(update),
        len(compressed_frame_stream),
        chunks=rl_stats.chunks,
        full=rl_stats.full_frames,
        ref=rl_stats.ref_frames,
        ok=(reconstructed == update),
        comparable=False,
        notes="gzip applied to modeled ReduLink frame stream",
    ))

    if zstd is not None:
        zwarm = zstd_bytes(warm)
        zupdate = zstd_bytes(update)
        if zwarm is not None and zupdate is not None:
            zr = redulink.run_bytes(zupdate, chunker="cdc", chunk_size=chunk_size, warm=zwarm)
            rows.append(stats_row(family, artifact, "warm-update-like", "cdc", "zstd-then-redulink", zr,
                                  notes="ReduLink applied after zstd compression"))

    return rows


def parse_artifact(value: str) -> tuple[str, Path, Path | None]:
    if "=" not in value:
        path = Path(value)
        return path.stem or "artifact", path, None
    label, path = value.split("=", 1)
    if ":" in path:
        warm, update = path.split(":", 1)
        return label, Path(update), Path(warm)
    return label, Path(path), None


def read_manifest(path: Path) -> list[str]:
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    specs: list[str] = []
    for row in rows:
        label = row.get("label", "").strip()
        artifact_path = row.get("path", "").strip()
        warm_path = row.get("warm_path", "").strip()
        update_path = row.get("update_path", "").strip()
        if not label:
            raise SystemExit(f"manifest row missing label: {row}")
        if warm_path and update_path:
            specs.append(f"{label}={warm_path}:{update_path}")
        elif artifact_path:
            specs.append(f"{label}={artifact_path}")
        else:
            raise SystemExit(f"manifest row needs path or warm_path/update_path: {row}")
    return specs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", action="append", default=[],
                        help="Artifact path, label=/path, or label=/warm/path:/update/path. May be repeated.")
    parser.add_argument("--manifest", action="append", default=[],
                        help="CSV manifest with label,path or label,warm_path,update_path columns.")
    parser.add_argument("--synthetic", action="append", choices=["logs", "updates", "mixed"], default=[],
                        help="Synthetic workload to include. May be repeated.")
    parser.add_argument("--output", default="results/baseline_comparison.csv")
    parser.add_argument("--chunk-size", type=int, default=8192)
    parser.add_argument("--warm-fraction", type=float, default=0.45)
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    for variant in args.synthetic:
        rows.extend(evaluate_artifact("synthetic", variant, synthetic_data(variant),
                                      chunk_size=args.chunk_size, warm_fraction=args.warm_fraction,
                                      warm_update=synthetic_warm_update(variant)))

    artifact_specs = list(args.artifact)
    for manifest in args.manifest:
        artifact_specs.extend(read_manifest(Path(manifest)))

    for spec in artifact_specs:
        label, path, warm_path = parse_artifact(spec)
        data = redulink.read_artifact(path)
        warm_update = None
        if warm_path is not None:
            warm_update = (redulink.read_artifact(warm_path), data)
        rows.extend(evaluate_artifact("public-artifact", label, data,
                                      chunk_size=args.chunk_size, warm_fraction=args.warm_fraction,
                                      warm_update=warm_update))

    if not rows:
        parser.error("provide at least one --synthetic or --artifact")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    write_metadata(out)
    print(out)


if __name__ == "__main__":
    main()
