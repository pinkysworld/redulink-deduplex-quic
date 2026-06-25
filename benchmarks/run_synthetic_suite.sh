#!/usr/bin/env bash
set -euo pipefail

out="results/synthetic_suite.csv"
smoke=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      out="$2"
      shift 2
      ;;
    --smoke)
      smoke=1
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$smoke" == "1" ]]; then
  python3 benchmarks/run_baseline_comparison.py \
    --synthetic logs \
    --output "$out"
else
  python3 benchmarks/run_baseline_comparison.py \
    --synthetic logs \
    --synthetic updates \
    --synthetic mixed \
    --output "$out"
fi
