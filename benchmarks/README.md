# Reproducible benchmark guide

The v3.16 manuscript uses exact reconstruction and byte accounting. Timing,
throughput, userspace shaping, kernel shaping, and competing-flow files are not
manuscript evidence.

## Public release pairs

Fetch and verify the pinned Click, Redis, and Nginx archives:

```bash
python benchmarks/fetch_external_public_corpora.py
```

Run raw-tree, named-object, rsync, and dictionary-compression evidence:

```bash
python benchmarks/run_real_workload_manifest.py \
  --manifest benchmarks/external_public_manifest.csv \
  --output results/external_public_suite.csv
python benchmarks/run_external_object_workload_suite.py \
  --output results/external_object_workload_suite.csv
python benchmarks/run_rsync_baseline_manifest.py \
  --manifest benchmarks/external_public_manifest.csv \
  --output results/rsync_baseline_external_public.csv
python benchmarks/run_framing_dictionary_baseline.py --sets local
```

The object suite serializes ordered relative names, lengths, and contents and
requires exact object-map reconstruction. Its binary HMAC-frame profile uses a
documented deterministic public artifact key to test serialization, tag
verification, and exactness, not key secrecy. It reports:

- ReduLink binary HMAC frames at their actual encoded length;
- a 4 KiB chunk-token baseline;
- true whole-object content addressing;
- gzip of the new serialized object stream.

The zstd baseline uses the complete prior object stream as a raw-content
dictionary at level 3 with a frame checksum. It pins window_log 21 for headline
rows and records window_log 24 as a sensitivity case. Both configurations
decompress with the same dictionary and require exact bytes and SHA-256. This is
a codec baseline, not an implementation of RFC 9842.

The raw-tree runner parses every message-length prefix and decodes HELLO, every
FRAME, END_ROUND, MISSING, and FINISH. Reconstruction consumes the decoded
frames rather than the original in-memory frame objects.

The gzip baseline fixes level 6 and mtime zero, records Python and zlib
versions, decompresses its output, and verifies exact bytes and SHA-256.

The rsync baseline runs GNU rsync 3.2.7 with recursive, symlink, checksum,
delete, no-whole-file, fixed-checksum-seed, and stats options. It reports the
observed median total sent plus received bytes across five runs and retains all
per-run totals. Every run must reconstruct exactly. The canonical tree manifest
commits to every relative path, entry type, length, file content, and symlink
target.

## PyPI wheel pairs

```bash
python benchmarks/run_pypi_version_pair_object_study.py
```

The result records both wheel hashes and exact ordered-member reconstruction.
Network retrieval is not required when the pinned wheels are supplied through
`--wheel-cache`.

## Native QUIC stream accounting

```bash
python benchmarks/run_quic_flow_comparison.py
python benchmarks/run_protocol_stream_accounting.py
```

The first command runs raw and ReduLink transfers over an actual encrypted
aioquic stream. The second produces a same-layer zero-loss table. ReduLink bytes
are split into forward protocol records, reverse repair/control messages, and a
diagnostic STATS response that is reported but excluded. The result does not
represent QUIC packet, UDP/IP, or link-layer bytes and is not a congestion-
fairness experiment.

## Workload controls, capacity, and misses

```bash
python benchmarks/run_aioquic_workload_cases.py
python benchmarks/run_object_chunk_size_sensitivity.py
python benchmarks/run_aioquic_scaling_experiment.py
python benchmarks/run_quic_miss_rate_sensitivity.py
python benchmarks/derive_deployment_envelope.py
```

The workload cases include a deterministic warm update, an independent
compressed negative control, and an author-constructed Redis-derived layer
fixture. The object sensitivity sweep holds dictionary capacity at a
byte-equivalent 64 MiB while varying fixed chunks from 0.5 to 16 KiB. The native
scaling sweep gives sender and receiver matched budgets and includes paired
16 MiB runs with 8,192 and 24,576 chunks. The miss sweep holds input and initial
reference count fixed while thinning receiver state through the 100 percent-miss
endpoint. Every row requires exact reconstruction.

The final command derives, and then mechanically verifies against every miss
row, the measured stream-byte equation and integer break-even. It also reports
the paired 16 MiB capacity result as a separate residency gate. This is not a
latency model or a workload-population estimate.

## Figures and validation

```bash
python scripts/make_journal_figures_v3_16.py
python scripts/build_manuscript_v3_16.py
python scripts/run_full_validation.py
```

The committed result files retain source versions, hashes, parameters, and
method-specific byte layers where the producing tool exposes them. The local
full validator rebuilds figures and a normalized DOCX in temporary paths and
extracts the PDF to check its source revision and load-bearing claims. CI
additionally regenerates benchmark tables and invokes the semantic comparison
mode before accepting committed evidence.
