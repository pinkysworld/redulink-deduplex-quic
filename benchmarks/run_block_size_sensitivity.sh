#!/usr/bin/env bash
set -euo pipefail

manifest="benchmarks/target_class_manifest.csv"
out_dir="results/block_size_sensitivity"
sizes=(2048 4096 8192 16384 32768)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      manifest="$2"
      shift 2
      ;;
    --output-dir)
      out_dir="$2"
      shift 2
      ;;
    --sizes)
      IFS=',' read -r -a sizes <<< "$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

python3 benchmarks/generate_target_corpora.py --manifest "$manifest"
mkdir -p "$out_dir"

for size in "${sizes[@]}"; do
  python3 benchmarks/run_baseline_comparison.py \
    --manifest "$manifest" \
    --family target-class \
    --chunk-size "$size" \
    --output "$out_dir/target_class_block_${size}.csv"
done

python3 benchmarks/check_generated_artifacts.py \
  --manifest "$manifest" \
  --results "$out_dir/target_class_block_8192.csv"
