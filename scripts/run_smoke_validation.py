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

def run_unittest_file(name: str) -> None:
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", name])

if __name__ == "__main__":
    run([sys.executable, "scripts/check_text_line_endings.py"])
    run([sys.executable, "scripts/check_manuscript_citations.py"])
    run([sys.executable, "benchmarks/check_generated_artifacts.py"])
    corpora = ROOT / "data" / "external_public_corpora"
    if corpora.exists() and any(corpora.iterdir()):
        run([sys.executable, "benchmarks/run_external_object_workload_suite.py"])
    else:
        print("~ skipping external object suite (corpora not fetched; run "
              "benchmarks/fetch_external_public_corpora.py to enable)", flush=True)
    for test_file in [
        "test_reconstruction.py",
        "test_secure_binding_hardening.py",
        "test_external_object_workload_suite.py",
        "test_redulink_wire.py",
        "test_key_schedule.py",
        "test_secure_verify_hardening.py",
    ]:
        run_unittest_file(test_file)
    print("smoke validation OK: line endings, citations, generated artifacts, and core security/model tests passed")
