#!/usr/bin/env bash
set -euo pipefail

out="results/public_artifact_suite.csv"
manifest=""
artifacts=()

usage() {
  cat <<'EOF'
Usage:
  benchmarks/run_public_artifacts.sh [--output results/public_artifact_suite.csv] label=/path/to/artifact [...]
  benchmarks/run_public_artifacts.sh --manifest benchmarks/public_artifacts_manifest.csv

Examples:
  benchmarks/run_public_artifacts.sh \
    ubuntu-base=/data/oci/ubuntu-22.04:/data/oci/ubuntu-24.04 \
    linux-kernel=/data/tarballs/linux-6.8:/data/tarballs/linux-6.9 \
    git-pack=/data/git-packs/repo-old:/data/git-packs/repo-new

The script accepts files or directories. Use label=warm_path:update_path for
version-pair runs. It does not download large corpora by default, so reviewers
can point it at reproducible public artifacts they fetched under their own
storage/network constraints.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      out="$2"
      shift 2
      ;;
    --manifest)
      manifest="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *=*)
      artifacts+=("$1")
      shift
      ;;
    *)
      echo "expected label=/path/to/artifact, got: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

artifact_count=${#artifacts[@]}
if [[ "$artifact_count" -eq 0 && -z "$manifest" ]]; then
  echo "no artifacts provided" >&2
  usage >&2
  exit 2
fi

cmd=(python3 benchmarks/run_baseline_comparison.py --output "$out")
if [[ -n "$manifest" ]]; then
  cmd+=(--manifest "$manifest")
fi
if [[ "$artifact_count" -gt 0 ]]; then
  for artifact in "${artifacts[@]}"; do
    cmd+=(--artifact "$artifact")
  done
fi
"${cmd[@]}"
