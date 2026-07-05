#!/usr/bin/env python3
"""Check reviewer-facing tracked text files use LF line endings.

GitHub Raw can make CR-heavy artifacts look compressed or hostile to reviewers.
This check keeps Markdown, CSV, JSON, scripts, and metadata files LF-only while
leaving binary manuscript artifacts alone.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".cff",
    ".csv",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {"Dockerfile", "LICENSE"}


def tracked_files() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [ROOT / line for line in out.splitlines() if line]


def is_reviewer_text(path: Path) -> bool:
    return path.suffix in TEXT_SUFFIXES or path.name in TEXT_NAMES


def main() -> None:
    bad: list[str] = []
    checked = 0
    for path in tracked_files():
        if not path.is_file() or not is_reviewer_text(path):
            continue
        checked += 1
        data = path.read_bytes()
        if b"\r" in data:
            rel = path.relative_to(ROOT)
            bad.append(f"{rel} contains CR/CRLF line endings")
    if bad:
        print("text line ending check failed:", file=sys.stderr)
        for item in bad:
            print(f"- {item}", file=sys.stderr)
        raise SystemExit(1)
    print(f"text line ending check OK: {checked} tracked text files are LF-only")


if __name__ == "__main__":
    main()
