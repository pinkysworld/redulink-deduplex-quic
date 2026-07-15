#!/usr/bin/env python3
"""Verify the manuscript files bound by MANUSCRIPT_SHA256.txt."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HASH_LINE = re.compile(r"^([0-9a-f]{64})  (\S.*)$")


def verify(manifest: Path) -> list[Path]:
    verified: list[Path] = []
    lines = manifest.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"empty hash manifest: {manifest}")
    for line_number, line in enumerate(lines, 1):
        match = HASH_LINE.fullmatch(line)
        if match is None:
            raise ValueError(
                f"{manifest}:{line_number}: expected '<64 lowercase hex>  <relative path>'"
            )
        expected, relative = match.groups()
        path = (ROOT / relative).resolve()
        try:
            path.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise ValueError(f"{manifest}:{line_number}: path escapes repository: {relative}") from exc
        if not path.is_file():
            raise FileNotFoundError(f"{manifest}:{line_number}: missing file: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(
                f"{manifest}:{line_number}: SHA-256 mismatch for {relative}: "
                f"expected {expected}, got {actual}"
            )
        verified.append(path)
    return verified


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=ROOT / "MANUSCRIPT_SHA256.txt")
    args = parser.parse_args()
    files = verify(args.manifest.resolve())
    for path in files:
        print(f"OK {path.relative_to(ROOT)}")
    print(f"manuscript hashes OK: {len(files)} files")


if __name__ == "__main__":
    main()
