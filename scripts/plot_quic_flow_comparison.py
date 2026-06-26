#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input', default='results/quic_flow_comparison.csv')
    p.add_argument('--output', default='figures/quic_flow_comparison.png')
    args=p.parse_args()
    rows=list(csv.DictReader(open(args.input)))
    labels=[f"{r['method'].replace('-',' ')}\nloss {r['loss_every']}" for r in rows]
    values=[float(r['effective_multiplier']) for r in rows]
    try:
        import matplotlib.pyplot as plt
        fig, ax=plt.subplots(figsize=(10,4.8))
        y=list(range(len(rows)))
        ax.barh(y, values)
        ax.axvline(1.0, linestyle='--', linewidth=1)
        ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel('Effective multiplier over QUIC stream payload bytes')
        ax.set_title('Raw QUIC versus ReduLink binary stream mapping')
        ax.grid(axis='x', alpha=.25)
        for i,v in enumerate(values): ax.text(v+0.05, i, f'{v:.2f}x', va='center')
        fig.tight_layout()
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.output, dpi=220)
    except Exception:
        from PIL import Image, ImageDraw
        w,h=1200,360; left=360; top=50; rowh=65; plotw=760; maxv=max(values)*1.2
        im=Image.new('RGB',(w,h),'white'); d=ImageDraw.Draw(im)
        d.text((left,20),'Raw QUIC versus ReduLink binary stream mapping', fill='black')
        for i,(lab,v) in enumerate(zip(labels, values)):
            y=top+i*rowh; d.text((20,y+10), lab, fill='black')
            bw=int(plotw*v/maxv); d.rectangle((left,y,left+bw,y+24), fill=(80,120,160)); d.text((left+bw+8,y+5),f'{v:.2f}x', fill='black')
        Path(args.output).parent.mkdir(parents=True, exist_ok=True); im.save(args.output)
    print(args.output)

if __name__=='__main__': main()
