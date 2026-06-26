# Reproducible Benchmarks

The benchmark suite is designed to make the paper tables reproducible from
plain CSV outputs. It separates small synthetic runs from larger public-artifact
runs so CI can stay fast while reviewers can rerun the stronger evidence path.
It also includes deterministic target-class fixtures for controlled positive,
weak, and negative cases.

## Synthetic suite

```bash
bash benchmarks/run_synthetic_suite.sh
```

Output:

```text
results/synthetic_suite.csv
```

This suite includes raw bytes, gzip, zstd when the `zstd` CLI is installed, a
fixed-block reuse approximation inspired by rsync-family delta transfer,
ReduLink fixed chunking, ReduLink CDC, gzip-before-ReduLink,
zstd-before-ReduLink when available, and ReduLink-before-gzip on the modeled
frame stream.

## Public artifact suite

For a small reproducible public-corpora fixture:

```bash
python3 benchmarks/fetch_public_corpora.py
bash benchmarks/run_public_artifacts.sh \
  --manifest benchmarks/public_artifacts_manifest.csv
```

For larger corpora under your local storage policy, point the benchmark at the
resulting files or directories:

```bash
bash benchmarks/run_public_artifacts.sh \
  ubuntu-base=/data/oci/ubuntu-22.04:/data/oci/ubuntu-24.04 \
  linux-kernel=/data/tarballs/linux-6.8:/data/tarballs/linux-6.9 \
  git-pack=/data/git-packs/repo-old:/data/git-packs/repo-new
```

Use `label=warm_path:update_path` for explicit version-pair runs. A manifest
file is preferred for paper artifacts because it can carry URLs, checksums, byte
sizes, license notes, and retrieval dates:

```bash
bash benchmarks/run_public_artifacts.sh \
  --manifest benchmarks/public_artifacts_manifest.csv
```

Recommended artifact families:

- OCI/container image layers, for example Ubuntu base layers across releases.
- Linux kernel release tarballs, for version-to-version delta behavior.
- Git pack snapshots of a medium-sized repository.
- Package metadata directories from Debian or Ubuntu mirrors.
- Structured log archives with repeated templates and fields.

Output:

```text
results/public_artifact_suite.csv
results/public_artifact_suite.csv.metadata.json
```

The file `benchmarks/public_artifacts_manifest.example.csv` shows the expected
manifest columns. Fill in exact source URLs, SHA256 hashes, byte sizes,
content-relation labels, license notes, and retrieval timestamps before using a
public-artifact table in a paper.

## Target-class generated suite

The target-class suite creates deterministic generated warm/update pairs for
software-update, container-layer, git-like, VM/backup, structured-log, random
negative-control, related-compressed, and independent-compressed negative-control
cases:

```bash
bash benchmarks/run_target_class_suite.sh
python3 benchmarks/check_generated_artifacts.py
```

Output:

```text
benchmarks/target_class_manifest.csv
results/target_class_suite.csv
results/target_class_suite.csv.metadata.json
```

These are controlled fixtures, not production traces. They are useful because
they show where ReduLink helps and where it does not. The related-compressed row
is a diagnostic positive case; the independent-compressed row is the true
compressed negative control.

Optional block-size sensitivity:

```bash
bash benchmarks/run_block_size_sensitivity.sh
```

## Cost columns

The baseline runner records `wall_ms`, `throughput_mib_s_local`,
`runner_peak_kib`, and `cost_scope`. These are local elapsed wall-clock
measurements, not machine-independent constants. `runner_peak_kib` is a coarse
process maximum RSS from `getrusage`; use it to expose resource scale, not to
compare implementations across machines. `cost_scope` distinguishes
compression-only rows, fixed-block scans, ReduLink encode/decode rows, and
composition diagnostics.

## Plot generation

After producing a benchmark CSV:

```bash
python3 scripts/plot_results.py results/synthetic_suite.csv --output-dir figures
```

The plotting script generates:

```text
figures/effective_multiplier_by_workload.png
figures/savings_by_workload.png
figures/effective_multiplier_warm_update.png
figures/savings_warm_update.png
figures/benchmark_summary.md
```

For the paper-facing warm/update summary:

```bash
python3 scripts/summarize_benchmark_evidence.py
python3 scripts/plot_warm_update_summary.py
```

Output:

```text
results/target_class_warm_update_summary.csv
figures/target_class/redulink_vs_baseline_warm_update.png
paper/evidence_tables.md
```

The plotting script supports both the baseline-suite schema and the selected
measurement schema used by `results/paper_real_artifact_cdc_selected.csv`.

## Diagnostic rows

Rows such as `redulink-then-gzip` compress a text serialization of modeled
frames and are marked `comparable=False`. They remain useful for diagnostics but
are excluded from plots and best-method summaries.

## UDP endpoint repair experiment

Run the localhost UDP endpoint experiment with semantic MISS repair and
retransmission:

```bash
bash benchmarks/run_udp_repair_experiment.sh
```

The command writes `results/udp_repair_experiment.json`.

## Wire-byte fairness accounting

The benchmark suite includes `run_wire_fairness_accounting.py` and the native aioquic stream-mapping experiment. This is a deterministic accounting sanity check: a ReduLink-encoded flow and a raw UDP-like competitor are served by encoded wire bytes. The result demonstrates that reconstructed application bytes do not inflate bottleneck service share.

```bash
python3 benchmarks/run_wire_fairness_accounting.py
```

This is not a competing-flow QUIC congestion-control experiment.
