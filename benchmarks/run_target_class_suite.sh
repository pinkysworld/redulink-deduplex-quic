#!/usr/bin/env bash
set -euo pipefail

manifest="benchmarks/target_class_manifest.csv"
out="results/target_class_suite.csv"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      manifest="$2"
      shift 2
      ;;
    --output)
      out="$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

python3 benchmarks/generate_target_corpora.py --manifest "$manifest"
python3 benchmarks/run_baseline_comparison.py \
  --manifest "$manifest" \
  --family target-class \
  --output "$out"
