#!/usr/bin/env python3
"""Run real rsync baselines on warm/update manifest pairs.

This complements the modeled fixed-block comparator. It uses the system rsync
binary with --no-whole-file so local runs still exercise rsync's delta-transfer
path. The command uses recursive checksum mode instead of archive mode so
owner, group, permission, and timestamp metadata are not part of the measured
baseline. It operates on temporary receiver copies and records rsync's own
--stats counters; it is not a ReduLink wire-compatible baseline.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RSYNC = shutil.which("rsync")
RSYNC_FLAGS = ["-r", "-l", "-c", "--delete", "--no-whole-file", "--stats"]


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
        "reconstruction_ok": str(after_bytes == new_bytes),
        "rsync_command": " ".join(cmd[:-2] + ["<new>", "<receiver>"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "rsync_baseline_manifest.csv")
    args = parser.parse_args()
    with args.manifest.open(newline="") as fh:
        manifest_rows = list(csv.DictReader(fh))
    if not manifest_rows:
        raise SystemExit("manifest has no rows")
    out_rows = [run_pair(row) for row in manifest_rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)
    print(args.output)


if __name__ == "__main__":
    main()
