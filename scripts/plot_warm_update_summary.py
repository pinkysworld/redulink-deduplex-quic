#!/usr/bin/env python3
"""Plot a paper-facing warm/update summary from target-class evidence."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def load(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", default="results/target_class_warm_update_summary.csv")
    parser.add_argument("--output", default="figures/target_class/redulink_vs_baseline_warm_update.png")
    args = parser.parse_args()

    rows = load(Path(args.summary))
    labels = [row["target"] for row in rows]
    fixed = [float(row["fixed_block_multiplier"]) for row in rows]
    rl_fixed = [float(row["redulink_fixed_multiplier"]) for row in rows]
    rl_cdc = [float(row["redulink_cdc_multiplier"]) for row in rows]

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        plot_with_pillow(rows, labels, fixed, rl_fixed, rl_cdc, Path(args.output))
        return

    y = list(range(len(rows)))
    height = 0.24
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    ax.barh([v - height for v in y], fixed, height=height, label="fixed-block baseline", color="#264653")
    ax.barh(y, rl_fixed, height=height, label="ReduLink fixed", color="#2a9d8f")
    ax.barh([v + height for v in y], rl_cdc, height=height, label="ReduLink CDC", color="#e9c46a")
    ax.axvline(1.0, color="#444444", linewidth=1.0, linestyle="--")
    ax.set_xscale("log")
    ax.set_xlabel("Effective multiplier over transmitted bytes (log scale)")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_title("Warm/update target-class evidence: ReduLink versus fixed-block baseline")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="lower right")
    for idx, row in enumerate(rows):
        best_rl = max(float(row["redulink_fixed_multiplier"]), float(row["redulink_cdc_multiplier"]))
        ax.text(max(best_rl, fixed[idx]) * 1.08, idx, f"best RL {best_rl:.2f}x", va="center", fontsize=8)
    fig.tight_layout()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220)
    plt.close(fig)
    print(output)


def plot_with_pillow(rows: list[dict[str, str]], labels: list[str], fixed: list[float],
                     rl_fixed: list[float], rl_cdc: list[float], output: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SystemExit("plotting requires either matplotlib or Pillow") from exc

    width = 1450
    row_h = 62
    height = 170 + row_h * len(rows)
    left = 250
    right = 130
    top = 90
    plot_w = width - left - right
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = load_font(18)
    small_font = load_font(15)
    title_font = load_font(22)
    colors = [(38, 70, 83), (42, 157, 143), (233, 196, 106)]

    max_value = max(max(fixed), max(rl_fixed), max(rl_cdc), 1.0)
    scale_max = max_value * 1.15

    draw.text((left, 24), "Warm/update target-class evidence: ReduLink versus fixed-block baseline",
              fill=(20, 20, 20), font=title_font)
    draw.text((left, 52), "Effective multiplier over transmitted bytes; dashed line marks 1.0x",
              fill=(70, 70, 70), font=small_font)

    for tick in [1, 2, 5, 10, 20]:
        if tick > scale_max:
            continue
        x = left + int((tick / scale_max) * plot_w)
        draw.line((x, top - 10, x, height - 70), fill=(224, 224, 224))
        draw.text((x - 10, height - 58), f"{tick}x", fill=(80, 80, 80), font=small_font)
    x_one = left + int((1 / scale_max) * plot_w)
    for y in range(top - 10, height - 70, 8):
        draw.line((x_one, y, x_one, y + 4), fill=(80, 80, 80))

    series = [("fixed-block", fixed), ("ReduLink fixed", rl_fixed), ("ReduLink CDC", rl_cdc)]
    for idx, label in enumerate(labels):
        y0 = top + idx * row_h
        draw.text((25, y0 + 18), label, fill=(30, 30, 30), font=small_font)
        for sidx, (_, values) in enumerate(series):
            y = y0 + 8 + sidx * 16
            x1 = left + int((values[idx] / scale_max) * plot_w)
            draw.rectangle((left, y, max(left + 2, x1), y + 11), fill=colors[sidx])
            draw.text((x1 + 6, y - 3), f"{values[idx]:.2f}x", fill=(45, 45, 45), font=small_font)

    legend_x = left
    legend_y = height - 35
    for sidx, (name, _) in enumerate(series):
        x = legend_x + sidx * 180
        draw.rectangle((x, legend_y, x + 14, legend_y + 14), fill=colors[sidx])
        draw.text((x + 20, legend_y), name, fill=(40, 40, 40), font=small_font)

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    print(output)


def load_font(size: int):
    from PIL import ImageFont

    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


if __name__ == "__main__":
    main()
