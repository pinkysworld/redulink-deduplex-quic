#!/usr/bin/env bash
set -euo pipefail
python3 benchmarks/generate_journal_corpora.py
python3 benchmarks/run_baseline_comparison.py \
  --manifest benchmarks/journal_workload_manifest.csv \
  --family journal-fixture \
  --output results/journal_workload_suite.csv \
  --chunk-size 4096
