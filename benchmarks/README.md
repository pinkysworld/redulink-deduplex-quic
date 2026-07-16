# Reproducible benchmark guide

The v3.17 manuscript separates deterministic byte evidence from paired
transport measurements. Current Linux kernel-path, multistream, fairness, and
CPU files are manuscript evidence. Historical asymmetric-clock timing and
userspace path-emulation files remain excluded.

## IBM production registry trace

Download the public archive linked by Anwar et al. (FAST 2018), verify its
published SHA-1, extract it outside the repository, and run:

```bash
python benchmarks/run_ibm_registry_trace_residency_v3_17.py \
  --trace-root /path/to/extracted-trace \
  --archive /path/to/DockerRegistryTraces.tar.gz
```

The complete run merges daily shards by timestamp and applies a true
byte-bounded LRU per anonymized client and availability zone. Production and
nonproduction zones are kept separate according to the source paper. The
result is an exact same-client full-blob residency upper bound because
authorization changes and client-local deletion are not present. It does not
measure within-blob alignment.

## Pinned public registry layers

```bash
python benchmarks/run_public_registry_layer_sensitivity_v3_17.py
```

The pinned manifest resolves Redis, httpd, and Alpine update pairs to immutable
index and linux/amd64 manifest digests. Every compressed blob is verified by
digest and length. Identical layers are removed as ordinary whole-layer CAS
hits before changed blobs are evaluated at 1, 4, and 16 KiB. Network caches are
stored under `/tmp` and are not submission files.

## Linux transport, streams, and fairness

The registered privileged workflow is
`.github/workflows/linux-netem-isolated.yml`. Its `full` profile runs:

```bash
python benchmarks/run_linux_netem_quic_path.py
python benchmarks/run_quic_multistream_experiment.py
python benchmarks/run_quic_competing_fairness_v3_17.py
```

The path matrix uses 5/20 Mbit/s, 20/80 ms RTT, 0/0.5% random loss, Reno, and
20 paired order-alternated rounds for two positive fixtures. Completion and
FIRST_BYTE use one client monotonic clock. Per-transfer root-qdisc counters
include encrypted handshake, ACK, loss, close, and the 13-byte measurement
acknowledgement. The multistream study uses one connection and actual stream
IDs. Fairness starts both established connections at a post-preparation
application barrier and computes Jain's index over encoded goodput.

## CPU and TTFB scaling

```bash
python benchmarks/run_cpu_throughput_scaling_v3_17.py
```

The paired local study covers 64 KiB through 32 MiB with one warmup, ten
order-alternated rounds, full garbage collection before each transfer, a fresh
verified connection, and combined in-process client plus server CPU. It is
Python implementation evidence, not a native-code throughput claim.

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
python scripts/make_submission_figures_v3_17.py
python scripts/build_manuscript_v3_17.py
python scripts/run_full_validation.py
```

The committed result files retain source versions, hashes, parameters, and
method-specific byte layers where the producing tool exposes them. The local
full validator rebuilds figures and a normalized DOCX in temporary paths and
extracts the PDF to check its source revision and load-bearing claims. CI
also validates the registered Linux result schemas and exact reconstruction.
