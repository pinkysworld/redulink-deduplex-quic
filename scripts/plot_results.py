#!/usr/bin/env python3
"""Create paper figures from ReduLink benchmark CSVs."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return normalize_rows(list(csv.DictReader(fh)))


def normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if not rows:
        return rows
    if "artifact" in rows[0] and "wire_bytes" in rows[0]:
        for row in rows:
            row.setdefault("comparable", "True")
        return rows
    if "family" in rows[0] and "wire_model_bytes" in rows[0]:
        normalized = []
        for row in rows:
            normalized.append({
                "family": "selected-artifact",
                "artifact": row["family"],
                "mode": row["mode"],
                "chunker": "cdc",
                "method": "redulink",
                "input_bytes": row["input_bytes"],
                "wire_bytes": row["wire_model_bytes"],
                "saving_rate": row["saving_rate"],
                "effective_multiplier": row["effective_multiplier"],
                "chunks": row["chunks"],
                "full_frames": row["full_frames"],
                "ref_frames": row["ref_frames"],
                "reconstruction_ok": "True",
                "comparable": "True",
                "notes": "normalized from selected measurement schema",
            })
        return normalized
    expected = "artifact/method/wire_bytes or family/wire_model_bytes"
    raise SystemExit(f"unsupported CSV schema; expected {expected}")


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        return None
    return plt


def grouped_best(rows: list[dict[str, str]], metric: str) -> tuple[list[str], list[str], dict[tuple[str, str], float]]:
    workloads = []
    methods = []
    values: dict[tuple[str, str], float] = {}
    for row in rows:
        if row.get("reconstruction_ok") == "False":
            continue
        if row.get("comparable", "True") == "False":
            continue
        workload = f"{row['artifact']}:{row['mode']}"
        method = f"{row['method']}:{row['chunker']}"
        workloads.append(workload)
        methods.append(method)
        values[(workload, method)] = float(row[metric])
    return sorted(set(workloads)), sorted(set(methods)), values


def plot_grouped(rows: list[dict[str, str]], metric: str, title: str, ylabel: str, output: Path) -> None:
    plt = require_matplotlib()
    workloads, methods, values = grouped_best(rows, metric)
    if not workloads or not methods:
        raise SystemExit("no plottable successful rows found")

    preferred = [
        "raw:none",
        "gzip-6:none",
        "zstd-3:none",
        "fixed-block-reuse:fixed",
        "rsync-block-reuse:fixed",
        "redulink:fixed",
        "redulink:cdc",
        "gzip-then-redulink:cdc",
        "zstd-then-redulink:cdc",
    ]
    methods = [m for m in preferred if m in methods]

    if plt is None:
        plot_grouped_pillow(workloads, methods, values, metric, title, ylabel, output)
        return

    width = max(0.08, min(0.8 / len(methods), 0.18))
    x_positions = list(range(len(workloads)))

    fig_width = max(10, len(workloads) * 1.25)
    fig, ax = plt.subplots(figsize=(fig_width, 6))
    for idx, method in enumerate(methods):
        offset = (idx - (len(methods) - 1) / 2) * width
        ys = [values.get((workload, method), 0.0) for workload in workloads]
        ax.bar([x + offset for x in x_positions], ys, width=width, label=method)

    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(workloads, rotation=35, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8, ncols=2)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_grouped_pillow(workloads: list[str], methods: list[str],
                        values: dict[tuple[str, str], float], metric: str,
                        title: str, ylabel: str, output: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SystemExit("plotting requires either matplotlib or Pillow") from exc

    palette = [
        (38, 70, 83),
        (42, 157, 143),
        (233, 196, 106),
        (230, 111, 81),
        (87, 117, 144),
        (144, 190, 109),
        (249, 132, 74),
    ]
    width = max(1200, 190 * len(workloads))
    height = 760
    margin_left = 95
    margin_right = 260
    margin_top = 70
    margin_bottom = 190
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    max_value = max(values.get((workload, method), 0.0) for workload in workloads for method in methods)
    if metric == "saving_rate":
        max_value = max(1.0, max_value)
    else:
        max_value = max(1.0, max_value) * 1.08

    draw.text((margin_left, 25), title, fill=(20, 20, 20), font=font)
    draw.text((15, margin_top + plot_h // 2), ylabel, fill=(20, 20, 20), font=font)

    for tick in range(6):
        y_value = max_value * tick / 5
        y = margin_top + plot_h - int((y_value / max_value) * plot_h)
        draw.line((margin_left, y, margin_left + plot_w, y), fill=(224, 224, 224))
        draw.text((margin_left - 70, y - 6), f"{y_value:.2f}", fill=(80, 80, 80), font=font)

    group_w = plot_w / max(1, len(workloads))
    bar_w = max(4, int(group_w / (len(methods) + 2)))
    for wi, workload in enumerate(workloads):
        group_x = margin_left + wi * group_w
        for mi, method in enumerate(methods):
            value = values.get((workload, method), 0.0)
            x0 = int(group_x + (mi + 0.5) * bar_w)
            x1 = x0 + bar_w - 2
            y1 = margin_top + plot_h
            y0 = y1 - int((value / max_value) * plot_h)
            draw.rectangle((x0, y0, x1, y1), fill=palette[mi % len(palette)])
        label = workload.replace("warm-update-like", "warm").replace("cold-intra-artifact", "cold")
        draw.text((int(group_x + 4), margin_top + plot_h + 12), label[:28], fill=(60, 60, 60), font=font)

    legend_x = margin_left + plot_w + 25
    legend_y = margin_top
    for mi, method in enumerate(methods):
        y = legend_y + mi * 24
        draw.rectangle((legend_x, y, legend_x + 14, y + 14), fill=palette[mi % len(palette)])
        draw.text((legend_x + 20, y), method, fill=(40, 40, 40), font=font)

    draw.line((margin_left, margin_top, margin_left, margin_top + plot_h), fill=(80, 80, 80))
    draw.line((margin_left, margin_top + plot_h, margin_left + plot_w, margin_top + plot_h), fill=(80, 80, 80))
    image.save(output)


def write_summary(rows: list[dict[str, str]], output: Path) -> None:
    by_workload: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("reconstruction_ok") != "False" and row.get("comparable", "True") != "False":
            by_workload[f"{row['artifact']}:{row['mode']}"].append(row)

    lines = ["# Benchmark Summary", ""]
    for workload, group in sorted(by_workload.items()):
        best = max(group, key=lambda r: float(r["effective_multiplier"]))
        lines.append(f"- {workload}: best {best['method']} ({best['chunker']}) "
                     f"multiplier={float(best['effective_multiplier']):.3f}, "
                     f"savings={float(best['saving_rate']):.3f}")
    lines.append("")
    lines.append("Rows marked comparable=False remain in the CSV but are excluded from plots and best-method summary selection.")
    output.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path")
    parser.add_argument("--output-dir", default="figures")
    args = parser.parse_args()

    rows = load_rows(Path(args.csv_path))
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    plot_grouped(
        rows,
        "effective_multiplier",
        "Effective reconstructed throughput multiplier by workload",
        "Multiplier over transmitted wire bytes",
        out / "effective_multiplier_by_workload.png",
    )
    plot_grouped(
        rows,
        "saving_rate",
        "Modeled wire-byte savings by workload",
        "Saving rate",
        out / "savings_by_workload.png",
    )
    write_summary(rows, out / "benchmark_summary.md")


if __name__ == "__main__":
    main()
