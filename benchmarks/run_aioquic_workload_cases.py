#!/usr/bin/env python3
"""Run native aioquic ReduLink on positive, negative, and external-positive workloads."""
from __future__ import annotations
import argparse, csv, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'prototypes'))
from redulink_aioquic_experiment import run_async, demo_payload  # type: ignore
import asyncio

CASES = [
    ('demo-positive', None, None, 'constructed byte-stable warm update'),
    ('independent-compressed-negative', 'data/journal_corpora/independent-compressed-negative/warm.bin', 'data/journal_corpora/independent-compressed-negative/update.bin', 'independent compressed negative control'),
    ('external-positive-redis-layered', 'data/external_positive_corpora/redis-layered-public-positive/warm.bin', 'data/external_positive_corpora/redis-layered-public-positive/update.bin', 'layer-like positive corpus derived from public Redis bytes'),
]

def read(path: str) -> bytes:
    return (ROOT/path).read_bytes()

async def one(label, warm, update, notes):
    stats = await run_async(warm=warm, data=update, chunk_size=1024, missing_every=7, wire_format='binary', loss_every=0, account_datagrams=False)
    return {
        'label': label,
        'notes': notes,
        'input_bytes': stats['input_bytes'],
        'stream_payload_bytes': stats['quic_stream_payload_total_bytes'],
        'forward_protocol_stream_bytes': stats['forward_protocol_stream_bytes'],
        'reverse_repair_control_stream_bytes': stats['reverse_repair_control_stream_bytes'],
        'diagnostic_stats_stream_bytes_excluded': stats['diagnostic_stats_stream_bytes'],
        'stream_payload_multiplier': stats['quic_stream_payload_multiplier_after_repair'],
        'semantic_misses': stats['semantic_misses'],
        'repair_full_frames': stats['repair_full_frames'],
        'reconstruction_ok': stats['reconstruction_ok'],
        'application_stream_id': stats['application_stream_id'],
        'tls_server_certificate_verified': stats['tls_server_certificate_verified'],
        'tls_client_certificate_used': stats['tls_client_certificate_used'],
        'tls_exporter_live': stats['tls_exporter_live'],
        'tls_exporter_outputs_match': stats['tls_exporter_outputs_match'],
        'tls_exporter_bridge': stats['tls_exporter_bridge'],
        'redulink_key_derivation': stats['redulink_key_derivation'],
        'tls_exporter_invocation': stats['tls_exporter_invocation'],
        'record_mac_transcript': stats['record_mac_transcript'],
        'chunk_size_bytes': stats['chunk_size_bytes'],
        'receiver_dictionary_thinning_every': stats['receiver_dictionary_thinning_every'],
        'sender_dictionary_budget_chunks': stats['sender_dictionary_budget_chunks'],
        'receiver_dictionary_budget_chunks': stats['receiver_dictionary_budget_chunks'],
        'sha256': hashlib.sha256(update).hexdigest(),
    }

async def main_async():
    rows=[]
    for label, warm_path, update_path, notes in CASES:
        if label=='demo-positive':
            warm, update = demo_payload(96)
        else:
            warm, update = read(warm_path), read(update_path)
        rows.append(await one(label, warm, update, notes))
    return rows

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-csv', type=Path, default=ROOT/'results/aioquic_workload_cases.csv')
    parser.add_argument('--output-json', type=Path, default=ROOT/'results/aioquic_workload_cases.json')
    args = parser.parse_args()
    rows = asyncio.run(main_async())
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open('w', newline='') as fh:
        writer=csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    args.output_json.write_text(json.dumps({'results': rows}, indent=2, sort_keys=True)+'\n')
    print(args.output_csv)
if __name__=='__main__': main()
