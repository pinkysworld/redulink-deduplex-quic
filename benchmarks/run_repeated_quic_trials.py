#!/usr/bin/env python3
"""Repeat the native aioquic comparison and summarize variance."""
from __future__ import annotations
import csv, json, statistics, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'benchmarks'))
from run_quic_flow_comparison import run_raw  # type: ignore
sys.path.insert(0, str(ROOT/'prototypes'))
from redulink_aioquic_experiment import run_experiment, demo_payload  # type: ignore

def summarize(vals):
    return {
        'n': len(vals),
        'mean': statistics.fmean(vals),
        'median': statistics.median(vals),
        'stdev': statistics.stdev(vals) if len(vals)>1 else 0.0,
        'min': min(vals),
        'max': max(vals),
    }

def main():
    n=3
    warm,data=demo_payload(96)
    raw_mult=[]; raw_ms=[]; rl_mult=[]; rl_ms=[]; rl_udp=[]
    rows=[]
    for i in range(n):
        raw=run_raw(data, account_datagrams=True)
        rl=run_experiment(payload_blocks=96, wire_format='binary', account_datagrams=True)
        raw_mult.append(float(raw['effective_stream_payload_multiplier']))
        raw_ms.append(float(raw['client_elapsed_ms']))
        rl_mult.append(float(rl['quic_stream_payload_multiplier_after_repair']))
        rl_ms.append(float(rl['client_elapsed_ms']))
        rl_udp.append(float(rl.get('approx_ipv4_udp_multiplier_seen', 0)))
        rows.append({'trial': i+1, 'raw_stream_multiplier': raw_mult[-1], 'raw_client_ms': raw_ms[-1], 'redulink_stream_multiplier': rl_mult[-1], 'redulink_udp_est_multiplier': rl_udp[-1], 'redulink_client_ms': rl_ms[-1], 'redulink_reconstruction_ok': rl['reconstruction_ok']})
    out=ROOT/'results/repeated_quic_trials.csv'
    with out.open('w', newline='') as fh:
        writer=csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    summary={
        'raw_stream_multiplier': summarize(raw_mult),
        'raw_client_ms': summarize(raw_ms),
        'redulink_stream_multiplier': summarize(rl_mult),
        'redulink_udp_est_multiplier': summarize(rl_udp),
        'redulink_client_ms': summarize(rl_ms),
    }
    (ROOT/'results/repeated_quic_trials_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n')
    sum_rows=[]
    for metric, stats in summary.items():
        sum_rows.append({'metric': metric, **{k: f'{v:.6f}' if isinstance(v,float) else v for k,v in stats.items()}})
    with (ROOT/'results/repeated_quic_trials_summary.csv').open('w', newline='') as fh:
        writer=csv.DictWriter(fh, fieldnames=list(sum_rows[0].keys()), lineterminator='\n')
        writer.writeheader(); writer.writerows(sum_rows)
    print(out)
if __name__=='__main__': main()
