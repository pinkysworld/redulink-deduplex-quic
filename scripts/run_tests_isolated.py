#!/usr/bin/env python3
"""Run unittest modules in separate processes with hard per-file timeouts."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PER_FILE_TIMEOUT_SECONDS = int(os.environ.get("REDULINK_TEST_TIMEOUT", "60"))

def main() -> int:
    files = sorted((ROOT / "tests").glob("test_*.py"))
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    total = 0
    for path in files:
        mod = "tests." + path.stem
        print(f"== {mod}", flush=True)
        cmd = [sys.executable, "-m", "unittest", mod, "-q"]
        try:
            cp = subprocess.run(cmd, cwd=ROOT, text=True, env=env, timeout=PER_FILE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            print(f"module timed out after {PER_FILE_TIMEOUT_SECONDS}s: {mod}", file=sys.stderr)
            return 124
        if cp.returncode != 0:
            print(f"module failed: {mod} (rc={cp.returncode})", file=sys.stderr)
            return cp.returncode
        total += 1
    print(f"isolated unittest modules OK: {total}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
