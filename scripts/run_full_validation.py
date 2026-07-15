#!/usr/bin/env python3
"""Full submission-artifact validation for ReduLink.

Runs citation/artifact checks and every unittest module in an isolated process.
All locked dependencies are required so a nominally successful full validation
cannot hide skipped native-QUIC or fixed-PDF checks.
"""
from __future__ import annotations
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MODULES = ("aioquic", "docx", "matplotlib", "pypdf", "zstandard")

def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)

if __name__ == "__main__":
    missing = [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        raise SystemExit(
            "full validation requires the locked environment; missing modules: "
            + ", ".join(missing)
        )
    run([sys.executable, "scripts/check_text_line_endings.py"])
    run([sys.executable, "scripts/check_manuscript_citations.py"])
    run([sys.executable, "scripts/check_manuscript_hashes.py"])
    run([sys.executable, "scripts/check_submission_evidence.py"])
    run([sys.executable, "scripts/run_tests_isolated.py"])
    print("full validation OK")
