#!/usr/bin/env python3
"""Run real rsync baselines on warm/update manifest pairs.

This complements the modeled fixed-block comparator. It uses the system rsync
binary with --no-whole-file so local runs still exercise rsync's delta-transfer
path. The command uses recursive checksum mode instead of archive mode so
owner, group, permission, and timestamp metadata are not part of the measured
baseline. It operates on temporary receiver copies and records rsync's own
--stats counters. The reported row is the observed median total-byte run across
an odd number of repetitions, with every total retained; it is not a ReduLink
wire-compatible baseline.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RSYNC = shutil.which("rsync")
RSYNC_FLAGS = [
    "-r", "-l", "-c", "--delete", "--no-whole-file", "--checksum-seed=0", "--stats",
]


def rsync_version() -> str:
    if RSYNC is None:
        raise SystemExit("rsync is not available")
    proc = subprocess.run(
        [RSYNC, "--version"], capture_output=True, text=True, check=True,
    )
    lines = (proc.stdout or proc.stderr).splitlines()
    return lines[0].strip() if lines else "unknown"


def as_path(row: dict[str, str], *names: str) -> Path:
    for name in names:
        value = row.get(name, "")
        if value:
            path = Path(value)
            return path if path.is_absolute() else ROOT / path
    raise KeyError(f"none of {names} present")


def materialize_pair(old_path: Path, new_path: Path, tmp: Path) -> tuple[Path, Path, Path]:
    old_src = tmp / "old_src"
    new_src = tmp / "new_src"
    dest = tmp / "receiver"
    old_src.mkdir()
    new_src.mkdir()
    dest.mkdir()
    if old_path.is_dir() and new_path.is_dir():
        shutil.copytree(old_path, old_src / "tree", dirs_exist_ok=True)
        shutil.copytree(new_path, new_src / "tree", dirs_exist_ok=True)
        shutil.copytree(old_path, dest / "tree", dirs_exist_ok=True)
        return old_src / "tree", new_src / "tree", dest / "tree"
    if old_path.is_file() and new_path.is_file():
        name = "artifact.bin"
        shutil.copy2(old_path, old_src / name)
        shutil.copy2(new_path, new_src / name)
        shutil.copy2(old_path, dest / name)
        return old_src / name, new_src / name, dest / name
    raise ValueError(f"path types differ or are unsupported: {old_path} {new_path}")


def total_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def exact_tree_manifest(path: Path) -> tuple[str, int]:
    """Hash ordered path, type, length, link target, and file content."""
    root = path.parent if path.is_file() or path.is_symlink() else path
    entries = [path] if path.is_file() or path.is_symlink() else sorted(
        path.rglob("*"), key=lambda item: item.relative_to(root).as_posix(),
    )
    digest = hashlib.sha256()
    count = 0
    for item in entries:
        relative = item.relative_to(root).as_posix() if item != path or path.is_dir() else path.name
        relative_bytes = relative.encode("utf-8")
        if item.is_symlink():
            kind = b"symlink"
            payload = os.readlink(item).encode("utf-8")
        elif item.is_dir():
            kind = b"directory"
            payload = b""
        elif item.is_file():
            kind = b"file"
            payload = item.read_bytes()
        else:
            raise ValueError(f"unsupported filesystem entry in rsync baseline: {item}")
        digest.update(len(relative_bytes).to_bytes(8, "big"))
        digest.update(relative_bytes)
        digest.update(len(kind).to_bytes(4, "big"))
        digest.update(kind)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        count += 1
    return digest.hexdigest(), count


def parse_int(text: str, *labels: str) -> int:
    for label in labels:
        match = re.search(rf"^{re.escape(label)}:\s+([0-9,]+)", text, flags=re.MULTILINE)
        if match:
            return int(match.group(1).replace(",", ""))
    return 0


def rsync_source_arg(path: Path) -> str:
    if path.is_dir():
        return str(path) + "/"
    return str(path)


def run_pair(row: dict[str, str]) -> dict[str, str]:
    if RSYNC is None:
        raise SystemExit("rsync is not available")
    label = row.get("label") or row.get("artifact") or row.get("workload") or "workload"
    old_path = as_path(row, "old_path", "warm_path")
    new_path = as_path(row, "new_path", "update_path")
    with tempfile.TemporaryDirectory(prefix="redulink-rsync-") as tmp_name:
        tmp = Path(tmp_name)
        _, new_src, dest = materialize_pair(old_path, new_path, tmp)
        before_bytes = total_bytes(dest)
        new_bytes = total_bytes(new_src)
        expected_manifest_sha256, expected_manifest_entries = exact_tree_manifest(new_src)
        cmd = [
            RSYNC,
            *RSYNC_FLAGS,
            rsync_source_arg(new_src),
            rsync_source_arg(dest),
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        stats = proc.stdout + "\n" + proc.stderr
        sent = parse_int(stats, "Total bytes sent", "Total sent")
        received = parse_int(stats, "Total bytes received", "Total received")
        literal = parse_int(stats, "Literal data", "Unmatched data")
        matched = parse_int(stats, "Matched data")
        total_size = parse_int(stats, "Total file size")
        transferred_size = parse_int(stats, "Total transferred file size")
        after_bytes = total_bytes(dest)
        reconstructed_manifest_sha256, reconstructed_manifest_entries = exact_tree_manifest(dest)
    return {
        "label": label,
        "old_path": str(old_path.relative_to(ROOT) if old_path.is_relative_to(ROOT) else old_path),
        "new_path": str(new_path.relative_to(ROOT) if new_path.is_relative_to(ROOT) else new_path),
        "old_payload_bytes": str(before_bytes),
        "new_payload_bytes": str(new_bytes),
        "rsync_total_bytes_sent": str(sent),
        "rsync_total_bytes_received": str(received),
        "rsync_control_plus_data_bytes": str(sent + received),
        "rsync_literal_data": str(literal),
        "rsync_matched_data": str(matched),
        "rsync_total_file_size": str(total_size),
        "rsync_total_transferred_file_size": str(transferred_size),
        "rsync_effective_multiplier_sent_only": f"{(new_bytes / sent) if sent else 0:.6f}",
        "rsync_effective_multiplier_control_plus_data": f"{(new_bytes / (sent + received)) if (sent + received) else 0:.6f}",
        "expected_manifest_sha256": expected_manifest_sha256,
        "reconstructed_manifest_sha256": reconstructed_manifest_sha256,
        "expected_manifest_entries": str(expected_manifest_entries),
        "reconstructed_manifest_entries": str(reconstructed_manifest_entries),
        "reconstruction_ok": str(
            after_bytes == new_bytes
            and expected_manifest_entries == reconstructed_manifest_entries
            and expected_manifest_sha256 == reconstructed_manifest_sha256
        ),
        "rsync_executable": RSYNC,
        "rsync_version": rsync_version(),
        "rsync_command": " ".join(cmd[:-2] + ["<new>", "<receiver>"]),
    }


def run_pair_repeated(row: dict[str, str], rounds: int) -> dict[str, str]:
    """Return the observed median-byte run and retain all per-run totals."""
    if rounds < 1 or rounds % 2 == 0:
        raise ValueError("rsync rounds must be a positive odd integer")
    observed = [run_pair(row) for _ in range(rounds)]
    if not all(item["reconstruction_ok"] == "True" for item in observed):
        raise ValueError(f"rsync reconstruction failed for {observed[0]['label']}")
    ordered = sorted(observed, key=lambda item: int(item["rsync_control_plus_data_bytes"]))
    representative = dict(ordered[rounds // 2])
    totals = [int(item["rsync_control_plus_data_bytes"]) for item in observed]
    representative.update({
        "rsync_rounds": str(rounds),
        "rsync_control_plus_data_bytes_per_round": ";".join(str(value) for value in totals),
        "rsync_control_plus_data_bytes_min": str(min(totals)),
        "rsync_control_plus_data_bytes_max": str(max(totals)),
        "all_rounds_reconstruction_ok": "True",
    })
    return representative


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=5,
                        help="positive odd number of rsync protocol runs per pair")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "rsync_baseline_manifest.csv")
    args = parser.parse_args()
    with args.manifest.open(newline="") as fh:
        manifest_rows = list(csv.DictReader(fh))
    if not manifest_rows:
        raise SystemExit("manifest has no rows")
    out_rows = [run_pair_repeated(row, args.rounds) for row in manifest_rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)
    print(args.output)


if __name__ == "__main__":
    main()
