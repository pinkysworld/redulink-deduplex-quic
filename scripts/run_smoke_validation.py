#!/usr/bin/env python3
"""Fast smoke validation for the ReduLink artifact.

This command is intentionally narrower than the full validation suite. It checks
that manuscript citations are consistent, external object evidence is
reproducible when its corpus is present, and core security/model tests pass.
Use run_full_validation.py for all tests and aioquic integration checks.
"""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile
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
    run([sys.executable, "scripts/check_manuscript_hashes.py"])
    corpora = ROOT / "data" / "external_public_corpora"
    if corpora.exists() and any(corpora.iterdir()):
        with tempfile.TemporaryDirectory(prefix="redulink-smoke-") as tmp:
            run([
                sys.executable, "benchmarks/run_external_object_workload_suite.py",
                "--output", str(Path(tmp) / "external_object_workload_suite.csv"),
            ])
    else:
        print("~ skipping external object suite (corpora not fetched; run "
              "benchmarks/fetch_external_public_corpora.py to enable)", flush=True)
    for test_file in [
        "test_reconstruction.py",
        "test_secure_binding_hardening.py",
        "test_external_object_workload_suite.py",
        "test_redulink_wire.py",
        "test_manuscript_hashes.py",
        "test_key_schedule.py",
        "test_secure_verify_hardening.py",
    ]:
        run_unittest_file(test_file)
    print("smoke validation OK: line endings, citations, manuscript hashes, and core tests passed")
