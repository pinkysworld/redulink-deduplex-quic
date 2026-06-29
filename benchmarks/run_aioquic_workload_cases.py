#!/usr/bin/env python3
"""Run native aioquic ReduLink on positive, negative, and external-positive workloads."""
from __future__ import annotations
import csv, hashlib, json, sys
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
    stats = await run_async(warm=warm, data=update, chunk_size=1024, missing_every=7, wire_format='binary', loss_every=0, account_datagrams=True)
    return {
        'label': label,
        'notes': notes,
        'input_bytes': stats['input_bytes'],
        'stream_payload_bytes': stats['quic_stream_payload_total_bytes'],
        'stream_payload_multiplier': stats['quic_stream_payload_multiplier_after_repair'],
        'udp_payload_bytes_seen_total': stats.get('udp_payload_bytes_seen_total',''),
        'approx_ipv4_udp_bytes_seen_total': stats.get('approx_ipv4_udp_bytes_seen_total',''),
        'approx_ipv4_udp_multiplier_seen': stats.get('approx_ipv4_udp_multiplier_seen',''),
        'semantic_misses': stats['semantic_misses'],
        'repair_full_frames': stats['repair_full_frames'],
        'reconstruction_ok': stats['reconstruction_ok'],
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
    out = ROOT/'results/aioquic_workload_cases.csv'
    rows = asyncio.run(main_async())
    with out.open('w', newline='') as fh:
        writer=csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    (ROOT/'results/aioquic_workload_cases.json').write_text(json.dumps({'results': rows}, indent=2, sort_keys=True)+'\n')
    print(out)
if __name__=='__main__': main()
