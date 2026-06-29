"""Generate additional journal figures for ReduLink v2.8.

Produces:
  figures/architecture/redulink_architecture.png  (static schematic)
  figures/block_size/block_size_sensitivity.png    (from journal_block_size_sensitivity.csv)

Quantitative content is read from result files so figures cannot drift from data.
"""
from __future__ import annotations
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
INK = "#1f2933"; ACCENT = "#2b6cb0"
SENDER = "#e6f0fb"; RECEIVER = "#e9f5ec"; STREAM = "#fdf3e0"; REPAIR = "#fdecea"


def _box(ax, x, y, w, h, text, face, *, fontsize=9, edge=INK, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        linewidth=1.3, edgecolor=edge, facecolor=face))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fontsize,
        color=INK, fontweight=("bold" if bold else "normal"))


def _arrow(ax, p0, p1, *, color=INK, style="-|>", lw=1.4, rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=12,
        linewidth=lw, color=color, connectionstyle=f"arc3,rad={rad}", linestyle=ls))


def architecture():
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    ax.set_xlim(0, 100); ax.set_ylim(0, 50); ax.axis("off")
    _box(ax, 2, 38, 26, 8, "Sender application\n(new byte stream)", SENDER, bold=True)
    _box(ax, 2, 27, 26, 8, "Chunker\nfixed / content-defined", SENDER)
    _box(ax, 2, 13.5, 26, 10.5,
         "Reference decision\nFULL (new chunk)  or\nREF (epoch, scope, stream id,\noffset, length, nonce, chunk id, HMAC)",
         SENDER, fontsize=7.6)
    _box(ax, 2, 4, 26, 7, "Compact binary FULL/REF/MISS records", SENDER, fontsize=8)
    _arrow(ax, (15, 38), (15, 35)); _arrow(ax, (15, 27), (15, 24))
    _arrow(ax, (15, 13.5), (15, 11))
    ax.add_patch(FancyBboxPatch((35, 4), 30, 42,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        linewidth=1.3, edgecolor=ACCENT, facecolor=STREAM))
    ax.text(50, 40, "aioquic QUIC stream\n(TLS 1.3 encrypted)", ha="center", va="center",
            fontsize=9.5, fontweight="bold", color=INK)
    ax.text(50, 33, "encoded bytes only on the wire;\ncongestion + fairness\naccount encoded bytes",
            ha="center", va="center", fontsize=8, color="#52606d")
    _arrow(ax, (28, 7.5), (35, 7.5), color=ACCENT, lw=1.8)
    ax.text(31.5, 9.4, "encode", ha="center", fontsize=7.5, color=ACCENT)
    _box(ax, 72, 38, 26, 8, "Receiver\nscoped warm dictionary", RECEIVER, bold=True)
    _box(ax, 72, 25, 26, 10, "Validate REF\nmembership + context + HMAC\n(fail-closed on mismatch)", RECEIVER, fontsize=8)
    _box(ax, 72, 14, 26, 8, "Reconstruct from dictionary\nbyte-exact", RECEIVER)
    _box(ax, 72, 4, 26, 7, "Reconstructed application bytes", RECEIVER, fontsize=8)
    _arrow(ax, (65, 7.5), (72, 7.5), color=ACCENT, lw=1.8)
    ax.text(68.5, 9.4, "decode", ha="center", fontsize=7.5, color=ACCENT)
    _arrow(ax, (85, 38), (85, 35)); _arrow(ax, (85, 25), (85, 22)); _arrow(ax, (85, 14), (85, 11))
    # Repair feedback: dashed loop arcing through the empty mid-band, no overlap
    _arrow(ax, (72, 26), (28, 18), color="#c0392b", rad=0.32, ls="--", lw=1.3)
    ax.text(50, 16.0, "MISS / fail-closed \u2192 request semantic FULL repair",
            ha="center", fontsize=7.6, color="#c0392b", fontweight="bold")
    ax.text(50, 48.4, "ReduLink: authenticated reference substitution over an encrypted QUIC stream",
            ha="center", fontsize=11, fontweight="bold", color=INK)
    ax.text(15, 0.8, "Endpoint (controls plaintext)", ha="center", fontsize=8, color="#52606d")
    ax.text(85, 0.8, "Endpoint (controls plaintext)", ha="center", fontsize=8, color="#52606d")
    out = FIG / "architecture" / "redulink_architecture.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight"); plt.close(fig); print(out)


def block_size():
    rows = list(csv.DictReader((ROOT/"results"/"journal_block_size_sensitivity.csv").open()))
    sizes = ["1024","2048","4096","8192","16384"]; size_kib = [1,2,4,8,16]
    artifacts = [("scripted-disk-snapshot","disk snapshot","#2b6cb0","o"),
                 ("scripted-oci-layer","oci layer","#2f855a","s"),
                 ("scripted-repository-snapshot","repository snapshot","#b7791f","^")]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for art,label,color,marker in artifacts:
        ys=[]
        for s in sizes:
            v=next((float(r["effective_multiplier"]) for r in rows
                    if r["artifact"]==art and r["chunker"]=="fixed" and r["chunk_size"]==s), None)
            ys.append(v)
        ax.plot(size_kib, ys, marker=marker, color=color, label=label, linewidth=1.8, markersize=6)
        for x,y in zip(size_kib, ys):
            ax.annotate(f"{y:.1f}", (x,y), textcoords="offset points", xytext=(0,6),
                        ha="center", fontsize=7, color=color)
    ax.axvline(4, color="#a0aec0", linestyle="--", linewidth=1)
    ax.set_xscale("log", base=2); ax.set_xticks(size_kib)
    ax.set_xticklabels([f"{s} KiB" for s in size_kib])
    ax.set_xlabel("Chunk / block size"); ax.set_ylabel("Effective stream-payload multiplier")
    ax.set_title("Block-size sensitivity (fixed chunking)")
    ax.grid(True, which="both", linestyle=":", linewidth=0.6, alpha=0.6)
    ax.legend(frameon=False, fontsize=8)
    ax.text(4, ax.get_ylim()[0], " 4 KiB default", fontsize=7.5, color="#718096", va="bottom")
    out = FIG / "block_size" / "block_size_sensitivity.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight"); plt.close(fig); print(out)


if __name__ == "__main__":
    architecture(); block_size()
