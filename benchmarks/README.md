# Reproducible Benchmarks

The benchmark suite is designed to make the paper tables reproducible from
plain CSV outputs. It separates small synthetic runs from larger public-artifact
runs so CI can stay fast while reviewers can rerun the stronger evidence path.

## Synthetic suite

```bash
bash benchmarks/run_synthetic_suite.sh
```

Output:

```text
results/synthetic_suite.csv
```

This suite includes raw bytes, gzip, zstd when the `zstd` CLI is installed, an
rsync-style rolling block reuse baseline, ReduLink fixed chunking, ReduLink CDC,
gzip-before-ReduLink, zstd-before-ReduLink when available, and
ReduLink-before-gzip on the modeled frame stream.

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
manifest columns. Fill in exact source URLs, SHA256 hashes, byte sizes, license
notes, and retrieval timestamps before using a public-artifact table in a paper.

## Plot generation

After producing a benchmark CSV:

```bash
python3 scripts/plot_results.py results/synthetic_suite.csv --output-dir figures
```

The plotting script generates:

```text
figures/effective_multiplier_by_workload.png
figures/savings_by_workload.png
```

The plotting script supports both the baseline-suite schema and the selected
measurement schema used by `results/paper_real_artifact_cdc_selected.csv`.

## Diagnostic rows

Rows such as `redulink-then-gzip` compress a text serialization of modeled
frames and are marked `comparable=False`. They remain useful for diagnostics but
are excluded from plots and best-method summaries.
