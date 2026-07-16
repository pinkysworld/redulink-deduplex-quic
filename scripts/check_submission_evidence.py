#!/usr/bin/env python3
"""Tie committed evidence, figures, and the editable manuscript together.

With ``--generated-dir``, compare regenerated CSV evidence against committed
load-bearing values while ignoring explicitly excluded diagnostics and recorded
environment provenance. Without it, validate source provenance and rebuild the
figures and DOCX in a temporary directory for normalized content comparison.
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
MANUSCRIPT = ROOT / "paper" / "submission" / "ReduLink_journal_ready_v3_16.docx"
PDF = ROOT / "paper" / "submission" / "ReduLink_journal_ready_v3_16.pdf"
FIGURES = ROOT / "figures" / "journal_v3_16"
SUBMISSION_FIGURE_NAMES = (
    "architecture.png",
    "dictionary_capacity_scaling.png",
    "object_chunk_size_sensitivity.png",
    "public_object_baselines.png",
    "semantic_miss_sensitivity.png",
)

# This is a CI reproduction gate, not uncertainty on the frozen result. With
# identical rsync 3.2.7 capabilities and delta-plan counters, Ubuntu 24.04
# emitted at most 0.591% fewer aggregate sent+received bytes than the frozen
# environment. The observed difference was confined to sender-side protocol
# overhead; every semantic and reconstruction field below remains exact.
RSYNC_PROTOCOL_TOTAL_RELATIVE_TOLERANCE = 0.01

CSV_KEYS = {
    "external_public_suite.csv": "label",
    "external_object_workload_suite.csv": "label",
    "framing_dictionary_baseline.csv": "label",
    "object_chunk_size_sensitivity.csv": ("label", "chunk_size_bytes"),
    "pypi_version_pair_object_study.csv": "package",
    "quic_flow_comparison.csv": "method",
    "protocol_stream_byte_accounting.csv": "experiment",
    "aioquic_workload_cases.csv": "label",
    "aioquic_scaling_experiment.csv": ("payload_blocks", "endpoint_dictionary_budget_chunks"),
    "quic_miss_rate_sensitivity.csv": "missing_every",
    "deployment_envelope.csv": "experiment",
}

EXCLUDED_COLUMNS = {
    "diagnostic_stats_stream_bytes",
    "diagnostic_stats_stream_bytes_excluded",
    "raw_diagnostic_stats_stream_bytes_excluded",
    "redulink_diagnostic_stats_stream_bytes_excluded",
    "gzip_python_version",
    "gzip_zlib_compile_version",
    "gzip_zlib_runtime_version",
    "rsync_executable",
    "rsync_command",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def row_key(row: dict[str, str], key: str | tuple[str, ...]) -> tuple[str, ...]:
    names = (key,) if isinstance(key, str) else key
    return tuple(row[name] for name in names)


def compare_csv(name: str, generated: Path) -> None:
    key = CSV_KEYS[name]
    expected_rows = {row_key(row, key): row for row in read_rows(RESULTS / name)}
    actual_rows = {row_key(row, key): row for row in read_rows(generated / name)}
    if set(actual_rows) != set(expected_rows):
        raise ValueError(f"{name}: regenerated row keys differ")
    for identity, expected in expected_rows.items():
        actual = actual_rows[identity]
        columns = set(expected) - EXCLUDED_COLUMNS
        if not columns.issubset(actual):
            raise ValueError(f"{name} {identity}: missing regenerated columns")
        for column in columns:
            if actual[column] != expected[column]:
                raise ValueError(
                    f"{name} {identity} {column}: expected {expected[column]!r}, "
                    f"got {actual[column]!r}"
                )


def compare_rsync(generated: Path) -> None:
    name = "rsync_baseline_external_public.csv"
    expected_rows = {row["label"]: row for row in read_rows(RESULTS / name)}
    actual_rows = {row["label"]: row for row in read_rows(generated / name)}
    if set(actual_rows) != set(expected_rows):
        raise ValueError("rsync regenerated row keys differ")
    exact_columns = [
        "old_payload_bytes", "new_payload_bytes", "expected_manifest_sha256",
        "reconstructed_manifest_sha256", "expected_manifest_entries",
        "reconstructed_manifest_entries", "reconstruction_ok",
        "all_rounds_reconstruction_ok", "rsync_rounds",
        "rsync_total_bytes_received", "rsync_literal_data",
        "rsync_matched_data", "rsync_total_file_size",
        "rsync_total_transferred_file_size",
    ]
    for label, expected in expected_rows.items():
        actual = actual_rows[label]
        for column in exact_columns:
            if actual[column] != expected[column]:
                raise ValueError(f"rsync {label} {column} changed")
        expected_total = int(expected["rsync_control_plus_data_bytes"])
        actual_total = int(actual["rsync_control_plus_data_bytes"])
        actual_sent = int(actual["rsync_total_bytes_sent"])
        actual_received = int(actual["rsync_total_bytes_received"])
        if actual_sent + actual_received != actual_total:
            raise ValueError(f"rsync {label}: sent+received does not equal total")
        actual_rounds = [
            int(value)
            for value in actual["rsync_control_plus_data_bytes_per_round"].split(";")
        ]
        if len(actual_rounds) != int(actual["rsync_rounds"]):
            raise ValueError(f"rsync {label}: per-round total count changed")
        ordered_rounds = sorted(actual_rounds)
        if actual_total != ordered_rounds[len(ordered_rounds) // 2]:
            raise ValueError(f"rsync {label}: recorded total is not the actual median")
        if int(actual["rsync_control_plus_data_bytes_min"]) != min(actual_rounds):
            raise ValueError(f"rsync {label}: recorded minimum is inconsistent")
        if int(actual["rsync_control_plus_data_bytes_max"]) != max(actual_rounds):
            raise ValueError(f"rsync {label}: recorded maximum is inconsistent")
        relative_changes = [
            abs(value - expected_total) / expected_total
            for value in [actual_total, *actual_rounds]
        ]
        if max(relative_changes) > RSYNC_PROTOCOL_TOTAL_RELATIVE_TOLERANCE:
            raise ValueError(
                f"rsync {label} protocol total changed by "
                f"{max(relative_changes):.3%}: "
                f"expected median {expected_total} from "
                f"[{expected['rsync_control_plus_data_bytes_per_round']}], "
                f"got median {actual_total} from "
                f"[{actual['rsync_control_plus_data_bytes_per_round']}]"
            )
        if "version 3.2.7  protocol version 31" not in actual["rsync_version"]:
            raise ValueError(f"rsync {label}: expected rsync 3.2.7 protocol 31")


def validate_source_commit() -> None:
    value = (ROOT / "SOURCE_COMMIT.txt").read_text(encoding="utf-8").strip()
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError("SOURCE_COMMIT.txt must contain one 40-hex commit")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", value, "HEAD"],
        cwd=ROOT, check=True,
    )


def validate_pdf_claims() -> None:
    """Check that the fixed-layout submission carries frozen provenance and claims."""

    if not PDF.is_file():
        raise ValueError("submission PDF is missing")
    text = " ".join(
        "\n".join((page.extract_text() or "") for page in PdfReader(str(PDF)).pages).split()
    )
    source_commit = (ROOT / "SOURCE_COMMIT.txt").read_text(encoding="utf-8").strip()
    required = (
        "ReduLink: Context-Bound Reference Substitution over Encrypted QUIC Streams",
        source_commit,
        "10.10x at 24,576 chunks",
        "B(m) = 15914 + 1149m",
        "live TLS exporter binding",
        "Declaration of Generative AI and AI-Assisted Technologies",
    )
    missing = [claim for claim in required if claim not in text]
    if missing:
        raise ValueError(f"submission PDF is missing load-bearing text: {missing}")


def compare_figures_and_docx() -> None:
    with tempfile.TemporaryDirectory(prefix="redulink-submission-check-") as tmp_name:
        tmp = Path(tmp_name)
        generated_figures = tmp / "figures"
        generated_docx = tmp / "manuscript.docx"
        subprocess.run([
            sys.executable, "scripts/make_journal_figures_v3_16.py",
            "--output-dir", str(generated_figures),
        ], cwd=ROOT, check=True)
        for name in SUBMISSION_FIGURE_NAMES:
            committed = FIGURES / name
            candidate = generated_figures / name
            if not committed.is_file() or candidate.read_bytes() != committed.read_bytes():
                raise ValueError(f"figure is stale relative to evidence: {name}")
        subprocess.run([
            sys.executable, "scripts/build_manuscript_v3_16.py",
            "--output", str(generated_docx),
            "--figures-dir", str(generated_figures),
        ], cwd=ROOT, check=True)
        with zipfile.ZipFile(MANUSCRIPT) as committed, zipfile.ZipFile(generated_docx) as regenerated:
            names = {
                name for name in committed.namelist()
                if name.startswith("word/") or name in {"[Content_Types].xml", "_rels/.rels"}
            }
            if not names.issubset(regenerated.namelist()):
                raise ValueError("regenerated DOCX package is incomplete")
            for name in names:
                if committed.read(name) != regenerated.read(name):
                    raise ValueError(f"manuscript is stale relative to evidence: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-dir", type=Path, default=None)
    args = parser.parse_args()
    validate_source_commit()
    validate_pdf_claims()
    if args.generated_dir is not None:
        for name in CSV_KEYS:
            compare_csv(name, args.generated_dir)
        compare_rsync(args.generated_dir)
        print("regenerated load-bearing evidence matches committed results")
    else:
        compare_figures_and_docx()
        print("source provenance, figures, and editable manuscript are synchronized")


if __name__ == "__main__":
    main()
