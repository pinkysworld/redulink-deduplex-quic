#!/usr/bin/env bash
set -euo pipefail
python3 benchmarks/generate_journal_corpora.py
bash benchmarks/run_journal_workload_suite.sh
python3 benchmarks/run_real_workload_manifest.py --manifest benchmarks/real_workload_manifest_from_journal.csv --output results/real_workload_suite.csv
python3 benchmarks/run_component_performance.py
python3 benchmarks/run_quic_flow_comparison.py
python3 benchmarks/run_quic_competing_flows.py --rounds 2 --loss-every 9
bash benchmarks/run_aioquic_experiment.sh
