#!/usr/bin/env python3
"""Generate the submission figures from the committed result tables."""

from __future__ import annotations

import argparse
import csv
import os
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
VERMILLION = "#D55E00"
PURPLE = "#CC79A7"
GRAY = "#666666"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def save(fig: plt.Figure, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for destination in (output, output.with_suffix(".pdf")):
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.stem}.",
                suffix=destination.suffix,
                dir=destination.parent,
            )
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                options = {"bbox_inches": "tight", "facecolor": "white"}
                if destination.suffix == ".png":
                    options["dpi"] = 320
                fig.savefig(temporary, **options)
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
    finally:
        plt.close(fig)


def architecture(output: Path) -> None:
    fig, ax = plt.subplots(figsize=(11.2, 4.8))
    ax.set_xlim(0, 11.2)
    ax.set_ylim(0, 5)
    ax.axis("off")

    def box(x: float, y: float, w: float, h: float, text: str, color: str) -> None:
        patch = FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.08",
            linewidth=1.8, edgecolor=color, facecolor="white",
        )
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=11)

    box(0.25, 2.65, 2.15, 1.25, "Sender\nchunk; choose\nFULL or REF", BLUE)
    box(2.9, 2.65, 2.5, 1.25, "HMAC record commitment\ncontext, offset,\nlength, nonce", ORANGE)
    box(5.95, 2.65, 1.9, 1.25, "QUIC stream\nTLS/AEAD", GREEN)
    box(8.4, 2.65, 2.15, 1.25, "Receiver\nverify;\nreconstruct", BLUE)
    box(0.55, 0.55, 1.65, 0.85, "Sender repair\nstate", GRAY)
    box(8.55, 0.55, 1.55, 0.85, "Scoped warm\ndictionary", GRAY)

    for start, end, color in [
        ((2.4, 3.28), (2.9, 3.28), BLUE),
        ((5.4, 3.28), (5.95, 3.28), ORANGE),
        ((7.85, 3.28), (8.4, 3.28), GREEN),
    ]:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=14,
                                     linewidth=1.8, color=color))
    ax.add_patch(FancyArrowPatch((9.1, 2.65), (9.25, 1.4), arrowstyle="-|>",
                                 mutation_scale=14, linewidth=1.5, color=GRAY))
    ax.add_patch(FancyArrowPatch((8.4, 2.9), (2.1, 1.1), arrowstyle="-|>",
                                 connectionstyle="arc3,rad=-0.18", mutation_scale=14,
                                 linewidth=1.7, color=VERMILLION))
    ax.add_patch(FancyArrowPatch((2.1, 1.1), (8.4, 2.75), arrowstyle="-|>",
                                 connectionstyle="arc3,rad=-0.12", mutation_scale=14,
                                 linewidth=1.7, color=PURPLE))
    ax.text(5.15, 1.35, "batched MISSING", color=VERMILLION, fontsize=10.5, ha="center")
    ax.text(5.25, 0.55, "authenticated FULL repairs", color=PURPLE, fontsize=10.5, ha="center")
    ax.text(7.9, 4.45, "Network attacker boundary\nQUIC/TLS", color=GREEN,
            fontsize=10.5, ha="center", va="center", weight="bold")
    ax.text(3.25, 4.45, "Defensive binding inside the endpoint\nnot a second network-security layer", color=ORANGE,
            fontsize=10.5, ha="center", va="center", weight="bold")
    ax.text(5.6, 0.05,
            "Warm state is preprovisioned or manifest-agreed; the prototype does not discover it on the wire.",
            fontsize=9.5, ha="center", color=GRAY)
    save(fig, output)


def object_comparison(results: Path, output: Path) -> None:
    objects = read_rows(results / "external_object_workload_suite.csv")
    zstd_rows = {
        row["label"].removeprefix("object-"): row
        for row in read_rows(results / "framing_dictionary_baseline.csv")
        if row["label"].startswith("object-")
    }
    labels = []
    values = []
    for row in objects:
        key = row["label"].replace("-object-sequence", "")
        labels.append(key.split("-")[0].capitalize())
        zkey = row["label"].replace("-object-sequence", "")
        zrow = zstd_rows[zkey]
        values.append([
            float(row["secure_multiplier"]),
            float(row["chunk_token_reuse_multiplier"]),
            float(row["whole_object_cas_multiplier"]),
            float(zrow["zstd_dictionary_multiplier"]),
            float(row["gzip_new_object_stream_multiplier"]),
        ])

    methods = ["ReduLink HMAC", "4 KiB token", "Whole-object CAS", "zstd prior-stream dict", "gzip"]
    colors = [BLUE, ORANGE, GREEN, PURPLE, GRAY]
    fig, axes = plt.subplots(1, len(labels), figsize=(11.2, 4.4), sharex=True, constrained_layout=True)
    for ax, label, row_values in zip(axes, labels, values):
        ypos = list(range(len(methods)))
        ax.barh(ypos, row_values, color=colors, edgecolor="black", linewidth=0.4)
        ax.axvline(1.0, color=VERMILLION, linestyle="--", linewidth=1.4)
        ax.set_xscale("log")
        ax.set_title(label, fontsize=12, weight="bold")
        ax.set_yticks(ypos, methods if ax is axes[0] else [])
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.25)
        for y, value in zip(ypos, row_values):
            ax.text(value * 1.04, y, f"{value:.2f}x", va="center", fontsize=8.5)
    axes[0].set_xlim(0.8, max(max(row) for row in values) * 1.35)
    fig.supxlabel("Reconstructed bytes / protocol or codec bytes (log scale)", fontsize=11)
    fig.text(0.995, 0.015, "Dashed line: break-even", ha="right", fontsize=9, color=VERMILLION)
    save(fig, output)


def scaling(results: Path, output: Path) -> None:
    rows = read_rows(results / "aioquic_scaling_experiment.csv")
    labels = []
    multipliers = []
    colors = []
    for row in rows:
        input_bytes = int(row["input_bytes"])
        size_label = (
            f"{input_bytes // 1024:g} KiB"
            if input_bytes < 1024 * 1024
            else f"{input_bytes / (1024 * 1024):g} MiB"
        )
        budget = int(row["endpoint_dictionary_budget_chunks"])
        labels.append(f"{size_label}\n{budget:,} chunks")
        value = float(row["stream_payload_multiplier"])
        multipliers.append(value)
        colors.append(VERMILLION if value < 1 else (GREEN if budget > 8192 else BLUE))
    fig, ax = plt.subplots(figsize=(10.2, 4.5), constrained_layout=True)
    bars = ax.bar(range(len(rows)), multipliers, color=colors, edgecolor="black", linewidth=0.5)
    ax.axhline(1.0, color=VERMILLION, linestyle="--", linewidth=1.5, label="break-even")
    ax.set_xticks(range(len(rows)), labels)
    ax.set_ylabel("Protocol-stream multiplier")
    ax.set_xlabel("Payload size and matched endpoint dictionary capacity")
    ax.set_ylim(0, max(multipliers) * 1.22)
    ax.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, multipliers):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.08, f"{value:.2f}x",
                ha="center", va="bottom", fontsize=9.5)
    save(fig, output)


def object_chunk_sensitivity(results: Path, output: Path) -> None:
    rows = read_rows(results / "object_chunk_size_sensitivity.csv")
    fig, ax = plt.subplots(figsize=(8.8, 4.5), constrained_layout=True)
    colors = {"click": BLUE, "redis": ORANGE, "nginx": GREEN}
    markers = {"click": "o", "redis": "s", "nginx": "^"}
    for label in ("click", "redis", "nginx"):
        selected = sorted(
            (row for row in rows if row["label"] == label),
            key=lambda row: int(row["chunk_size_bytes"]),
        )
        ax.plot(
            [int(row["chunk_size_bytes"]) / 1024 for row in selected],
            [float(row["multiplier"]) for row in selected],
            marker=markers[label], linewidth=2.0, color=colors[label],
            label=label.capitalize(),
        )
    ax.axhline(1.0, color=VERMILLION, linestyle="--", linewidth=1.4)
    ax.set_xscale("log", base=2)
    ax.set_xticks([0.5, 1, 2, 4, 8, 16], ["0.5", "1", "2", "4", "8", "16"])
    ax.set_xlabel("Fixed chunk size (KiB); dictionary capacity held at 64 MiB")
    ax.set_ylabel("Binary HMAC-frame profile multiplier")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    save(fig, output)


def miss_sensitivity(results: Path, output: Path) -> None:
    rows = read_rows(results / "quic_miss_rate_sensitivity.csv")
    miss_pct = [100 * float(row["miss_fraction"]) for row in rows]
    multiplier = [float(row["protocol_stream_multiplier"]) for row in rows]
    reverse = [int(row["reverse_repair_control_stream_bytes"]) for row in rows]
    fig, ax = plt.subplots(figsize=(8.8, 4.5), constrained_layout=True)
    ax.plot(miss_pct, multiplier, marker="o", linewidth=2.2, color=BLUE,
            label="protocol-stream multiplier")
    ax.axhline(1.0, color=VERMILLION, linestyle="--", linewidth=1.4)
    ax.set_xlabel("Receiver REF misses (% of initial REF frames)")
    ax.set_ylabel("Protocol-stream multiplier", color=BLUE)
    ax.tick_params(axis="y", labelcolor=BLUE)
    ax.grid(alpha=0.25)
    ax2 = ax.twinx()
    ax2.plot(miss_pct, reverse, marker="s", linewidth=2.0, color=ORANGE,
             label="reverse repair/control bytes")
    ax2.set_ylabel("Reverse repair/control bytes", color=ORANGE)
    ax2.tick_params(axis="y", labelcolor=ORANGE)
    lines = ax.get_lines()[:1] + ax2.get_lines()
    ax.legend(lines, [line.get_label() for line in lines], loc="center right", frameon=False)
    save(fig, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "figures" / "journal_v3_15")
    args = parser.parse_args()
    architecture(args.output_dir / "architecture.png")
    object_comparison(args.results_dir, args.output_dir / "public_object_baselines.png")
    object_chunk_sensitivity(args.results_dir, args.output_dir / "object_chunk_size_sensitivity.png")
    scaling(args.results_dir, args.output_dir / "dictionary_capacity_scaling.png")
    miss_sensitivity(args.results_dir, args.output_dir / "semantic_miss_sensitivity.png")
    print(args.output_dir)


if __name__ == "__main__":
    main()
