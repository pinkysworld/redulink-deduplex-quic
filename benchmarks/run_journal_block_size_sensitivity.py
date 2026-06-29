#!/usr/bin/env python3
"""Run a compact ReduLink block-size sensitivity table for selected fixtures."""
from __future__ import annotations
import csv, sys, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import redulink_model as model  # type: ignore
SIZES=[1024,2048,4096,8192,16384]
ARTIFACTS=['scripted-disk-snapshot','scripted-oci-layer','scripted-repository-snapshot']
OUT=ROOT/'results/journal_block_size_sensitivity.csv'

def read_manifest():
    subprocess.run([sys.executable, 'benchmarks/generate_journal_corpora.py'], cwd=ROOT, check=True, stdout=subprocess.PIPE)
    with (ROOT/'benchmarks/journal_workload_manifest.csv').open(newline='') as fh:
        return {r['label']: r for r in csv.DictReader(fh)}

def main():
    m=read_manifest(); rows=[]
    for art in ARTIFACTS:
        warm=(ROOT/m[art]['warm_path']).read_bytes(); update=(ROOT/m[art]['update_path']).read_bytes()
        for size in SIZES:
            for chunker in ['fixed','cdc']:
                st=model.run_bytes(update, warm=warm, chunker=chunker, chunk_size=size)
                rows.append({'artifact':art,'chunker':chunker,'chunk_size':size,'effective_multiplier':f'{st.effective_multiplier:.6f}','wire_bytes':st.wire_bytes,'chunks':st.chunks,'full_frames':st.full_frames,'ref_frames':st.ref_frames,'reconstruction_ok':st.reconstruction_ok})
    with OUT.open('w', newline='') as fh:
        writer=csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    print(OUT)
if __name__=='__main__': main()
