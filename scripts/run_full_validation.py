#!/usr/bin/env python3
"""Full reviewer validation for ReduLink.

Runs citation/artifact checks and every unittest module in an isolated process.
Aioquic-dependent tests skip gracefully when aioquic is not installed; install
requirements-dev.txt for complete QUIC stream validation.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)

if __name__ == "__main__":
    run([sys.executable, "scripts/check_manuscript_citations.py"])
    run([sys.executable, "benchmarks/check_generated_artifacts.py"])
    run([sys.executable, "scripts/run_tests_isolated.py"])
    print("full validation OK")
