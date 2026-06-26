#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/prototypes/redulink_aioquic_experiment.py" --wire-format json --output "$ROOT/results/aioquic_json_baseline_experiment.json" >/dev/null
python3 "$ROOT/prototypes/redulink_aioquic_experiment.py" --wire-format binary --output "$ROOT/results/aioquic_binary_experiment.json" >/dev/null
cp "$ROOT/results/aioquic_binary_experiment.json" "$ROOT/results/aioquic_native_experiment.json"
python3 "$ROOT/prototypes/redulink_aioquic_experiment.py" --wire-format binary --loss-every 9 --output "$ROOT/results/aioquic_binary_lossy_experiment.json" >/dev/null
python3 - <<'PY'
import csv, json
from pathlib import Path
root = Path(__file__).resolve().parents[1] if '__file__' in globals() else Path.cwd()
# The heredoc is executed from the caller's working directory in CI; prefer cwd.
if not (root / 'results').exists():
    root = Path.cwd()
rows = []
for label, name in [
    ('json-baseline', 'aioquic_json_baseline_experiment.json'),
    ('binary', 'aioquic_binary_experiment.json'),
    ('binary-lossy', 'aioquic_binary_lossy_experiment.json'),
]:
    d = json.loads((root / 'results' / name).read_text())
    rows.append({
        'case': label,
        'wire_format': d['wire_format'],
        'loss_every': d['datagram_loss_every'],
        'input_bytes': d['input_bytes'],
        'stream_payload_bytes': d['quic_stream_payload_total_bytes'],
        'stream_payload_multiplier': d['quic_stream_payload_multiplier_after_repair'],
        'semantic_misses': d['semantic_misses'],
        'repair_full_frames': d['repair_full_frames'],
        'dropped_datagrams': d.get('proxy_client_to_server_datagrams_dropped', 0) + d.get('proxy_server_to_client_datagrams_dropped', 0),
        'reconstruction_ok': d['reconstruction_ok'],
    })
with (root / 'results' / 'aioquic_experiment_summary.csv').open('w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
PY
cat "$ROOT/results/aioquic_experiment_summary.csv"
