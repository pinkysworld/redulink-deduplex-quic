#!/usr/bin/env python3
"""Generate paper-facing evidence tables from benchmark CSV outputs."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "results/target_class_suite.csv"
PUBLIC = ROOT / "results/public_artifact_suite.csv"
SYNTHETIC = ROOT / "results/synthetic_suite.csv"
SUMMARY_CSV = ROOT / "results/target_class_warm_update_summary.csv"
OUT_MD = ROOT / "paper/evidence_tables.md"


INTERPRETATION = {
    "software-update-generated": "ReduLink loses; single-object compression dominates this generated update shape.",
    "container-layer-generated": "Weak reference identity; fixed-block baseline helps more than ReduLink.",
    "git-packlike-generated": "Modest warm-dictionary gain, especially with CDC.",
    "vm-backup-generated": "Strong for aligned/page-like state; fixed-block and ReduLink fixed both benefit.",
    "structured-logs-generated": "Compression dominates; reference substitution is weak after overhead.",
    "random-negative-generated": "Correct no-gain random control.",
    "compressed-related-warm-generated": "Diagnostic positive: related compressed streams retain reusable byte regions.",
    "independent-compressed-negative-generated": "Correct no-gain compressed negative control.",
}


LABEL = {
    "software-update-generated": "software update",
    "container-layer-generated": "container layer",
    "git-packlike-generated": "git-packlike",
    "vm-backup-generated": "VM backup",
    "structured-logs-generated": "structured logs",
    "random-negative-generated": "random negative",
    "compressed-related-warm-generated": "compressed related",
    "independent-compressed-negative-generated": "compressed negative",
}


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def fnum(value: str, digits: int = 3) -> str:
    if value == "":
        return ""
    return f"{float(value):.{digits}f}"


def wall(row: dict[str, str]) -> str:
    return row.get("wall_ms") or row.get("cpu_ms") or ""


def mibps(row: dict[str, str]) -> str:
    return row.get("throughput_mib_s_local") or row.get("throughput_mib_s") or ""


def best(rows_: list[dict[str, str]], artifact: str, methods: set[str],
         mode: str | None = None, chunker: str | None = None) -> dict[str, str] | None:
    candidates = []
    for row in rows_:
        if row["artifact"] != artifact:
            continue
        if row["method"] not in methods:
            continue
        if mode is not None and row["mode"] != mode:
            continue
        if chunker is not None and row["chunker"] != chunker:
            continue
        if row.get("reconstruction_ok") == "False" or row.get("comparable", "True") == "False":
            continue
        candidates.append(row)
    if not candidates:
        return None
    return max(candidates, key=lambda r: float(r["effective_multiplier"]))


def exact(rows_: list[dict[str, str]], artifact: str, method: str,
          mode: str, chunker: str) -> dict[str, str]:
    for row in rows_:
        if (row["artifact"], row["method"], row["mode"], row["chunker"]) == (artifact, method, mode, chunker):
            return row
    raise KeyError((artifact, method, mode, chunker))


def make_target_summary(target_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    artifacts = []
    for row in target_rows:
        if row["mode"] == "warm-update-like" and row["artifact"] not in artifacts:
            artifacts.append(row["artifact"])

    out = []
    for artifact in artifacts:
        compression = best(target_rows, artifact, {"gzip-6", "zstd-3"}, mode="single-object")
        fixed_baseline = exact(target_rows, artifact, "fixed-block-reuse", "warm-update-like", "fixed")
        rl_fixed = exact(target_rows, artifact, "redulink", "warm-update-like", "fixed")
        rl_cdc = exact(target_rows, artifact, "redulink", "warm-update-like", "cdc")
        best_rl = max([rl_fixed, rl_cdc], key=lambda r: float(r["effective_multiplier"]))
        out.append({
            "artifact": artifact,
            "target": LABEL.get(artifact, artifact),
            "input_bytes": rl_fixed["input_bytes"],
            "warm_bytes": rl_fixed["warm_bytes"],
            "aligned_changed_bytes": rl_fixed["aligned_changed_bytes"],
            "best_compression_method": compression["method"] if compression else "",
            "best_compression_multiplier": compression["effective_multiplier"] if compression else "",
            "fixed_block_multiplier": fixed_baseline["effective_multiplier"],
            "redulink_fixed_multiplier": rl_fixed["effective_multiplier"],
            "redulink_cdc_multiplier": rl_cdc["effective_multiplier"],
            "best_redulink_method": best_rl["chunker"],
            "best_redulink_multiplier": best_rl["effective_multiplier"],
            "best_redulink_ref_frames": best_rl["ref_frames"],
            "best_redulink_wall_ms": wall(best_rl),
            "best_redulink_mibps": mibps(best_rl),
            "interpretation": INTERPRETATION.get(artifact, ""),
        })
    return out


def write_summary_csv(summary_rows: list[dict[str, str]]) -> None:
    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)


def md_target_table(summary_rows: list[dict[str, str]]) -> list[str]:
    lines = [
        "## Target-Class Evidence Matrix",
        "",
        "Source: `results/target_class_suite.csv` and `results/target_class_warm_update_summary.csv`. These are controlled generated fixtures, not production traces.",
        "",
        "| Target | Input bytes | Warm bytes | Changed bytes | Best compression | Fixed-block | ReduLink fixed | ReduLink CDC | Interpretation |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['target']} | {int(row['input_bytes']):,} | {int(row['warm_bytes']):,} | "
            f"{int(row['aligned_changed_bytes']):,} | {row['best_compression_method']} {fnum(row['best_compression_multiplier'])}x | "
            f"{fnum(row['fixed_block_multiplier'])}x | {fnum(row['redulink_fixed_multiplier'])}x | "
            f"{fnum(row['redulink_cdc_multiplier'])}x | {row['interpretation']} |"
        )
    lines.extend([
        "",
        "Interpretation: ReduLink helps only when byte-identical chunks survive across warm dictionary state and chosen chunk boundaries. The target-class suite deliberately includes weak and negative cases, because related data does not automatically imply referenceable chunk identity.",
        "",
    ])
    return lines


def md_public_coverage() -> list[str]:
    return [
        "## Public-Corpus Coverage and Limits",
        "",
        "| Corpus family | Current fixture | Scale | Positive cases | Negative/weak cases | Production trace? | Limitation |",
        "|---|---|---:|---|---|---|---|",
        "| Text version pairs | Yes | 23 KB-829 KB | nginx, redis | cpython, linux-parameters, RFC pair | No | Small, text-only, smoke-level public fixture. |",
        "| Public source-release snapshots | Yes | 0.95 MB-15.53 MB updates | None at fixed 4 KiB | Click, Redis, nginx | No | External public corpus, but not production traces. |",
        "| OCI/container layers | No | - | - | - | No | Needed for claimed container workloads. |",
        "| Git packs | No | - | - | - | No | Needed for repository synchronization claims. |",
        "| Package repository metadata | No | - | - | - | No | Needed for software-update claims. |",
        "| VM/backup snapshots | No | - | - | - | No | Needed beyond generated sparse-block fixture. |",
        "| Structured log archives | No | - | - | - | No | Needed beyond generated log fixture. |",
        "",
    ]


def md_public_excerpt(public_rows: list[dict[str, str]]) -> list[str]:
    selected = [
        ("nginx-changes", "fixed-block-reuse", "fixed"),
        ("nginx-changes", "redulink", "cdc"),
        ("redis-readme", "redulink", "cdc"),
        ("cpython-http-server", "redulink", "cdc"),
        ("linux-kernel-parameters", "redulink", "cdc"),
        ("ietf-quic-rfc", "redulink", "cdc"),
    ]
    lines = [
        "## Frozen Public-Corpora Fixture Excerpt",
        "",
        "Source: `results/public_artifact_suite.csv` and `benchmarks/public_artifacts_manifest.csv`.",
        "",
        "| Artifact | Method | Input bytes | Warm bytes | Changed bytes | Wire bytes | Multiplier | Wall ms | MiB/s local |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for artifact, method, chunker in selected:
        row = exact(public_rows, artifact, method, "warm-update-like", chunker)
        lines.append(
            f"| {artifact} | {method}:{chunker} | {int(row['input_bytes']):,} | "
            f"{int(row['warm_bytes']):,} | {int(row['aligned_changed_bytes']):,} | "
            f"{int(row['wire_bytes']):,} | {fnum(row['effective_multiplier'])}x | "
            f"{fnum(wall(row))} | {fnum(mibps(row))} |"
        )
    lines.extend([
        "",
        "Interpretation: the public fixture is intentionally small but pinned and checksum-verifiable. It contains one strong public changed-version case, one modest positive case, and several weak cases.",
        "",
    ])
    return lines


def md_synthetic_excerpt(synthetic_rows: list[dict[str, str]]) -> list[str]:
    selected = [
        ("logs", "redulink", "fixed"),
        ("logs", "redulink", "cdc"),
        ("updates", "redulink", "fixed"),
        ("mixed", "redulink", "fixed"),
        ("mixed", "redulink", "cdc"),
    ]
    lines = [
        "## Synthetic Excerpt",
        "",
        "Synthetic rows are retained as mechanism checks and should not be read as production trace validation.",
        "",
        "| Workload | Method | Input bytes | Wire bytes | Multiplier | Wall ms | MiB/s local |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for artifact, method, chunker in selected:
        row = exact(synthetic_rows, artifact, method, "warm-update-like", chunker)
        lines.append(
            f"| {artifact} | {method}:{chunker} | {int(row['input_bytes']):,} | "
            f"{int(row['wire_bytes']):,} | {fnum(row['effective_multiplier'])}x | "
            f"{fnum(wall(row))} | {fnum(mibps(row))} |"
        )
    lines.append("")
    return lines


def main() -> None:
    target_rows = rows(TARGET)
    public_rows = rows(PUBLIC)
    synthetic_rows = rows(SYNTHETIC)
    summary_rows = make_target_summary(target_rows)
    write_summary_csv(summary_rows)

    lines = [
        "# Version 2.3 Evidence Tables",
        "",
        "These tables are generated from repository CSV outputs. They emphasize evidence level, raw byte context, wall-clock cost scope, and negative controls.",
        "",
        "## Evidence Levels",
        "",
        "| Level | What it supports | Current repository artifact |",
        "|---|---|---|",
        "| Representation model | FULL/REF byte reconstruction, accounting, miss failure. | `src/redulink_model.py`, `tests/`. |",
        "| Controlled target fixtures | Target-class behavior under deterministic generated warm/update pairs. | `benchmarks/generate_target_corpora.py`, `results/target_class_suite.csv`. |",
        "| Frozen public fixture | Reviewer-runnable pinned public text/version pairs. | `benchmarks/public_artifacts_manifest.csv`, `results/public_artifact_suite.csv`. |",
        "| Prototype | Endpoint cooperation over localhost TCP/UDP and native QUIC stream mapping. | `prototypes/redulink_socket_prototype.py`, `prototypes/redulink_udp_repair_experiment.py`, `prototypes/redulink_authenticated_udp_experiment.py`, `prototypes/redulink_aioquic_experiment.py`. |",
        "| Pending transport validation | Custom QUIC extension frames, competing-flow congestion fairness, migration, 0-RTT, exporter-derived keys. | Not implemented. |",
        "",
    ]
    lines.extend(md_target_table(summary_rows))
    lines.extend(md_public_coverage())
    lines.extend(md_public_excerpt(public_rows))
    lines.extend(md_synthetic_excerpt(synthetic_rows))

    # Native aioquic stream-mapping result, if present.
    aioquic_path = ROOT / "results" / "aioquic_native_experiment.json"
    if aioquic_path.exists():
        import json
        q = json.loads(aioquic_path.read_text(encoding="utf-8"))
        lines.extend([
            "## Native aioquic Stream-Mapping Result",
            "",
            "Source: `results/aioquic_native_experiment.json`. This experiment uses a real aioquic client/server handshake and bidirectional QUIC stream on localhost. ReduLink messages are carried inside QUIC STREAM data; custom extension frames are not implemented.",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Input bytes | {int(q['input_bytes']):,} |",
            f"| Initial FULL / REF frames | {q['client_full_frames_initial']} / {q['client_ref_frames_initial']} |",
            f"| Semantic misses | {q['semantic_misses']} |",
            f"| Repair FULL frames | {q['client_repair_full_frames_sent']} |",
            f"| QUIC stream payload bytes after repair | {int(q['quic_stream_payload_total_bytes']):,} |",
            f"| Effective stream-payload multiplier after repair | {float(q['quic_stream_payload_multiplier_after_repair']):.3f}x |",
            f"| Reconstruction | {'byte-exact' if q['reconstruction_ok'] else 'failed'} |",
            f"| aioquic version | {q['aioquic_version']} |",
            "",
        ])
    lines.extend([
        "## Fixed-Block Baseline Definition",
        "",
        "| Parameter | Value |",
        "|---|---|",
        "| Default block size | 8192 bytes unless `--chunk-size` overrides it. |",
        "| Match rule | Byte-scan exact block match using a prefix lookup followed by full-block equality. |",
        "| Token overhead | 16 bytes per matched block reference. |",
        "| Literal overhead | 20 bytes per literal run plus literal bytes. |",
        "| Checksum exchange | Not modeled. |",
        "| rsync compatibility | No; this is an rsync-family fixed-block reuse approximation, not the rsync protocol. |",
        "| Compression order | None for fixed-block rows. |",
        "",
        "## Timing Scope",
        "",
        "`wall_ms`, `throughput_mib_s_local`, and `runner_peak_kib` are local runner measurements. They are not line-rate performance claims. `cost_scope` distinguishes compression-only rows, fixed-block scans, ReduLink encode/decode rows, and composition diagnostics.",
        "",
    ])
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(OUT_MD)
    print(SUMMARY_CSV)


if __name__ == "__main__":
    main()
