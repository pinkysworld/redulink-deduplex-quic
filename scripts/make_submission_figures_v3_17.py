#!/usr/bin/env python3
"""Generate the submission figures from the committed result tables."""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
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


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    # Keep the reverse control and repair paths in separate orthogonal lanes.
    # The earlier crossing Bezier curves obscured both labels near the receiver.
    ax.plot([8.72, 8.72, 2.55], [2.65, 1.78, 1.78], color=VERMILLION,
            linewidth=1.8, solid_capstyle="round")
    ax.add_patch(FancyArrowPatch((2.55, 1.78), (2.08, 1.32), arrowstyle="-|>",
                                 mutation_scale=14, linewidth=1.8,
                                 color=VERMILLION))
    ax.plot([2.16, 7.92, 7.92], [0.78, 0.78, 2.24], color=PURPLE,
            linewidth=1.8, solid_capstyle="round")
    ax.add_patch(FancyArrowPatch((7.92, 2.24), (8.43, 2.79), arrowstyle="-|>",
                                 mutation_scale=14, linewidth=1.8,
                                 color=PURPLE))
    label_box = {"facecolor": "white", "edgecolor": "none", "alpha": 0.96, "pad": 1.8}
    ax.text(5.15, 1.94, "batched MISSING", color=VERMILLION, fontsize=10.5,
            ha="center", va="center", bbox=label_box)
    ax.text(5.15, 0.94, "authenticated FULL repairs", color=PURPLE, fontsize=10.5,
            ha="center", va="center", bbox=label_box)
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


def production_gates(results: Path, output: Path) -> None:
    trace = [
        row for row in read_rows(results / "ibm_registry_trace_residency_v3_17.csv")
        if row["deployment_class"] == "production"
    ]
    layers = read_json(results / "public_registry_layer_chunk_sensitivity_v3_17.json")
    layer_rows = layers["aggregate_by_chunk_size"]

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.4), constrained_layout=True)
    ax = axes[0]
    budgets = [float(row["budget_mib_per_client"]) for row in trace]
    request_hits = [100 * float(row["warm_request_hit_fraction"]) for row in trace]
    byte_hits = [100 * float(row["warm_byte_hit_fraction"]) for row in trace]
    ax.plot(budgets, request_hits, marker="o", linewidth=2.2, color=BLUE,
            label="repeated blob requests")
    ax.plot(budgets, byte_hits, marker="s", linewidth=2.2, color=ORANGE,
            label="repeated blob bytes")
    ax.set_xscale("log", base=2)
    ax.set_xticks(budgets, ["64", "256", "1,024"])
    ax.set_xlabel("Per-client exact-blob LRU budget (MiB)")
    ax.set_ylabel("Warm residency upper bound (%)")
    ax.set_title("(a) IBM production trace: residency gate", weight="bold")
    ax.set_ylim(0, 27)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, loc="upper left")
    for x, y in zip(budgets, byte_hits):
        ax.annotate(f"{y:.1f}%", (x, y), xytext=(0, -15),
                    textcoords="offset points", ha="center", fontsize=8.5)

    ax = axes[1]
    chunks = [int(row["chunk_size_bytes"]) / 1024 for row in layer_rows]
    matched = [100 * float(row["matched_chunk_byte_fraction_within_changed_layers"])
               for row in layer_rows]
    changed_multiplier = [
        float(row["redulink_multiplier_vs_whole_layer_cas_changed_bytes"])
        for row in layer_rows
    ]
    bars = ax.bar(range(len(chunks)), matched, color=GREEN, edgecolor="black",
                  linewidth=0.5, width=0.58, label="exact matches in changed layers")
    ax.set_xticks(range(len(chunks)), [f"{value:g}" for value in chunks])
    ax.set_xlabel("Fixed chunk size (KiB)")
    ax.set_ylabel("Exact reusable bytes in changed layers (%)", color=GREEN)
    ax.tick_params(axis="y", labelcolor=GREEN)
    ax.set_ylim(0, 0.16)
    ax.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, matched):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.006,
                f"{value:.3f}%", ha="center", fontsize=8.5)
    ax2 = ax.twinx()
    ax2.plot(range(len(chunks)), changed_multiplier, marker="D", linewidth=2.0,
             color=VERMILLION, label="changed-layer byte multiplier")
    ax2.axhline(1.0, color=GRAY, linestyle="--", linewidth=1.2)
    ax2.set_ylabel("Changed bytes / ReduLink bytes", color=VERMILLION)
    ax2.tick_params(axis="y", labelcolor=VERMILLION)
    ax2.set_ylim(0.88, 1.015)
    ax.set_title("(b) Pinned compressed layers: alignment gate", weight="bold")
    ax.text(0.03, 0.94, "whole-layer CAS already avoids 26.65% of update bytes",
            transform=ax.transAxes, va="top", fontsize=8.7,
            bbox={"facecolor": "white", "edgecolor": "0.75", "pad": 2.5})
    save(fig, output)


def kernel_transport(results: Path, output: Path) -> None:
    rows = read_rows(results / "linux_netem_quic_path_v3_17_summary.csv")
    fig, axes = plt.subplots(2, 1, figsize=(11.2, 6.2), sharex=True,
                             constrained_layout=True)
    for ax, payload, panel in zip(axes, ("demo", "redis"), ("a", "b")):
        selected = sorted(
            (row for row in rows if row["payload"] == payload),
            key=lambda row: (
                float(row["rate_mbps"]), float(row["rtt_ms"]),
                float(row["loss_percent"]),
            ),
        )
        x = list(range(len(selected)))
        completion = [float(row["client_completion_ratio_mean"]) for row in selected]
        completion_low = [
            value - float(row["client_completion_ratio_ci95_low"])
            for value, row in zip(completion, selected)
        ]
        completion_high = [
            float(row["client_completion_ratio_ci95_high"]) - value
            for value, row in zip(completion, selected)
        ]
        ttfb = [float(row["client_ttfb_ratio_mean"]) for row in selected]
        ttfb_low = [
            value - float(row["client_ttfb_ratio_ci95_low"])
            for value, row in zip(ttfb, selected)
        ]
        ttfb_high = [
            float(row["client_ttfb_ratio_ci95_high"]) - value
            for value, row in zip(ttfb, selected)
        ]
        ax.errorbar(x, completion, yerr=[completion_low, completion_high], marker="o",
                    capsize=3, linewidth=1.8, color=BLUE,
                    label="client completion")
        ax.errorbar(x, ttfb, yerr=[ttfb_low, ttfb_high], marker="s",
                    capsize=3, linewidth=1.8, color=ORANGE,
                    label="client TTFB")
        ax.axhline(1.0, color=VERMILLION, linestyle="--", linewidth=1.2)
        ax.set_ylabel("ReduLink / raw QUIC")
        payload_title = "Constructed positive control" if payload == "demo" else "Redis-derived positive fixture"
        ax.set_title(f"({panel}) {payload_title}", weight="bold")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, ncol=2, loc="upper left")
    labels = [
        f"{float(row['rate_mbps']):g}M\n{float(row['rtt_ms']):g} ms\n{float(row['loss_percent']):g}%"
        for row in selected
    ]
    axes[-1].set_xticks(range(len(labels)), labels)
    axes[-1].set_xlabel("Path rate / RTT / random loss; Reno; 20 paired rounds")
    save(fig, output)


def streams_and_fairness(results: Path, output: Path) -> None:
    stream = read_json(results / "quic_multistream_experiment_v3_17.json")["aggregate"]
    fairness = read_json(results / "quic_competing_fairness_v3_17.json")["summary"]
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.6), constrained_layout=True)

    ax = axes[0]
    fields = [
        ("Small mean", "small_mean_completion_ratio"),
        ("Small tail", "small_tail_completion_ratio"),
        ("Blocker", "blocker_completion_ratio"),
        ("Session", "session_completion_ratio"),
    ]
    values = [float(stream[f"{key}_mean"]) for _, key in fields]
    low = [value - float(stream[f"{key}_ci95_low"])
           for value, (_, key) in zip(values, fields)]
    high = [float(stream[f"{key}_ci95_high"]) - value
            for value, (_, key) in zip(values, fields)]
    colors = [GREEN, GREEN, VERMILLION, GRAY]
    ax.bar(range(len(fields)), values, yerr=[low, high], capsize=4,
           color=colors, edgecolor="black", linewidth=0.5)
    ax.axhline(1.0, color=VERMILLION, linestyle="--", linewidth=1.2)
    ax.set_xticks(range(len(fields)), [label for label, _ in fields])
    ax.set_ylabel("Multiplexed / sequential completion")
    ax.set_title("(a) One QUIC connection, five streams", weight="bold")
    ax.set_ylim(0, 1.45)
    ax.grid(axis="y", alpha=0.25)
    ax.text(0.03, 0.94, "all small streams finish before the blocker",
            transform=ax.transAxes, va="top", fontsize=8.7)

    ax = axes[1]
    labels = ["Raw / raw", "ReduLink /\nReduLink", "Raw /\nReduLink"]
    values = [float(row["encoded_goodput_jain_fairness_mean"]) for row in fairness]
    low = [value - float(row["encoded_goodput_jain_fairness_ci95_low"])
           for value, row in zip(values, fairness)]
    high = [float(row["encoded_goodput_jain_fairness_ci95_high"]) - value
            for value, row in zip(values, fairness)]
    ax.bar(range(len(labels)), values, yerr=[low, high], capsize=4,
           color=[BLUE, ORANGE, PURPLE], edgecolor="black", linewidth=0.5)
    ax.set_xticks(range(len(labels)), labels)
    ax.set_ylabel("Jain fairness of encoded goodput")
    ax.set_title("(b) Synchronized competing Reno flows", weight="bold")
    ax.set_ylim(0.84, 1.01)
    ax.grid(axis="y", alpha=0.25)
    save(fig, output)


def cpu_scaling(results: Path, output: Path) -> None:
    summary = read_rows(results / "cpu_throughput_scaling_v3_17_summary.csv")
    raw = read_rows(results / "cpu_throughput_scaling_v3_17.csv")
    labels = [
        f"{float(row['input_mib']):g}" if float(row["input_mib"]) >= 1
        else f"{int(float(row['input_mib']) * 1024)} KiB"
        for row in summary
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), constrained_layout=True)

    ax = axes[0]
    x = list(range(len(summary)))
    completion = [float(row["completion_ratio_median"]) for row in summary]
    completion_low = [
        value - float(row["completion_ratio_median_ci95_low"])
        for value, row in zip(completion, summary)
    ]
    completion_high = [
        float(row["completion_ratio_median_ci95_high"]) - value
        for value, row in zip(completion, summary)
    ]
    cpu = [float(row["process_cpu_ratio_median"]) for row in summary]
    cpu_low = [value - float(row["process_cpu_ratio_median_ci95_low"])
               for value, row in zip(cpu, summary)]
    cpu_high = [float(row["process_cpu_ratio_median_ci95_high"]) - value
                for value, row in zip(cpu, summary)]
    ax.errorbar(x, completion, yerr=[completion_low, completion_high], marker="o",
                capsize=3, linewidth=1.8, color=BLUE, label="completion")
    ax.errorbar(x, cpu, yerr=[cpu_low, cpu_high], marker="s", capsize=3,
                linewidth=1.8, color=ORANGE, label="process CPU")
    ax.axhline(1.0, color=VERMILLION, linestyle="--", linewidth=1.2)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Median ReduLink / raw QUIC")
    ax.set_xlabel("Input size (MiB unless marked)")
    ax.set_title("(a) Paired localhost scaling", weight="bold")
    ax.set_ylim(0.75, 1.06)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)

    grouped: dict[tuple[int, str], list[float]] = {}
    for row in raw:
        grouped.setdefault((int(row["input_bytes"]), row["method"]), []).append(
            float(row["client_ttfb_ms"])
        )
    sizes = [int(row["input_bytes"]) for row in summary]
    raw_ttfb = [statistics.median(grouped[(size, "raw-quic-stream")]) for size in sizes]
    redulink_ttfb = [
        statistics.median(grouped[(size, "redulink-binary-quic-stream")])
        for size in sizes
    ]
    ax = axes[1]
    ax.plot(x, raw_ttfb, marker="o", linewidth=2.0, color=BLUE, label="raw QUIC")
    ax.plot(x, redulink_ttfb, marker="s", linewidth=2.0, color=VERMILLION,
            label="ReduLink")
    ax.set_yscale("log")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Median client TTFB (ms, log scale)")
    ax.set_xlabel("Input size (MiB unless marked)")
    ax.set_title("(b) Pre-encoding delays first byte", weight="bold")
    ax.grid(alpha=0.25, which="both")
    ax.legend(frameon=False)
    save(fig, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "figures" / "submission_v3_17")
    args = parser.parse_args()
    architecture(args.output_dir / "architecture.png")
    production_gates(args.results_dir, args.output_dir / "production_gates.png")
    kernel_transport(args.results_dir, args.output_dir / "kernel_path_transport.png")
    streams_and_fairness(args.results_dir, args.output_dir / "quic_streams_and_fairness.png")
    cpu_scaling(args.results_dir, args.output_dir / "cpu_scaling.png")
    print(args.output_dir)


if __name__ == "__main__":
    main()
