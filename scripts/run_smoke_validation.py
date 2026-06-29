#!/usr/bin/env python3
"""Fast reviewer smoke validation for the ReduLink artifact.

This command is intentionally narrower than the full validation suite. It checks
that the manuscript citations are consistent, generated fixtures are present,
external object evidence is reproducible, and core security/model tests pass.
It should complete quickly on a reviewer machine. Use run_full_validation.py for
all tests and optional aioquic integration checks.
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
    run([sys.executable, "benchmarks/run_external_object_workload_suite.py"])
    run([sys.executable, "-m", "unittest", "tests.test_reconstruction", "tests.test_secure_binding_hardening", "tests.test_external_object_workload_suite", "tests.test_redulink_wire", "tests.test_key_schedule"])
    print("smoke validation OK")
