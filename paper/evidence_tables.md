# Version 2.4 Evidence Tables

These tables summarize repository CSV outputs for the journal-ready package. They emphasize evidence level, raw byte context, wall-clock scope, negative controls, rsync comparison, and the distinction between QUIC stream payload bytes, local UDP payload bytes, and full packet-capture evidence.

## Evidence Levels

| Level | What it supports | Current repository artifact |
|---|---|---|
| Representation model | FULL/REF byte reconstruction, accounting, miss failure. | `src/redulink_model.py`, `tests/`. |
| Controlled target fixtures | Target-class behavior under deterministic generated warm/update pairs. | `benchmarks/generate_target_corpora.py`, `results/target_class_suite.csv`. |
| Journal fixtures | Disk, OCI-like, package-metadata, repository, log, and compressed negative cases. | `benchmarks/generate_journal_corpora.py`, `results/journal_workload_suite.csv`. |
| Frozen public text fixture | Reviewer-runnable pinned public text/version pairs, including positive nginx changes.xml case. | `benchmarks/public_artifacts_manifest.csv`, `results/public_artifact_suite.csv`. |
| External public source releases | Hash-pinned Click, Redis, and nginx release snapshots. | `benchmarks/fetch_external_public_corpora.py`, `benchmarks/external_public_manifest.csv`, `results/external_public_suite.csv`. |
| Real rsync baseline | Actual system rsync with `--no-whole-file` on source-release pairs. | `benchmarks/run_rsync_baseline_manifest.py`, `results/rsync_baseline_external_public.csv`. |
| Native QUIC stream prototype | Endpoint cooperation over TLS-protected aioquic streams. | `prototypes/redulink_aioquic_experiment.py`, `results/quic_flow_comparison.csv`. |
| Pending transport validation | Custom QUIC extension frames, full packet capture, tc/netem competing-flow fairness, migration, 0-RTT, exporter-derived keys. | Not implemented. |

## Journal Workload Excerpt

Source: `results/journal_workload_suite.csv`. These are deterministic scripted fixtures, not production traces.

| Workload | Chunker | Input bytes | Warm bytes | ReduLink bytes | ReduLink multiplier | Fixed-block multiplier | Interpretation |
|---|---|---:|---:|---:|---:|---:|---|
| scripted-disk-snapshot | fixed | 1,048,576 | 1,048,576 | 36,808 | 28.488x | 31.973x | Strong aligned/page-like positive case. |
| scripted-oci-layer | fixed | 296,960 | 296,960 | 26,864 | 11.054x | 10.682x | Positive generated layer-like case. |
| scripted-package-metadata | fixed | 365,878 | 365,012 | 372,830 | 0.981x | 0.984x | Negative; overhead exceeds reusable identity. |
| scripted-repository-snapshot | cdc | 760,820 | 744,755 | 493,838 | 1.541x | 1.568x | Modest repository-like gain. |
| scripted-structured-logs | fixed | 1,497,080 | 1,254,740 | 1,503,896 | 0.995x | 0.998x | Compression/text structure dominates. |
| independent-compressed-negative | fixed | 786,678 | 786,678 | 789,046 | 0.997x | 1.000x | Correct no-gain negative control. |

Interpretation: ReduLink helps only when byte-identical chunks survive across warm dictionary state and chosen chunk boundaries. Related content does not automatically imply referenceable chunk identity.

## External Public Source-Release Suite

Source: `benchmarks/external_public_manifest.csv`, `results/external_public_suite.csv`, and `results/rsync_baseline_external_public.csv`.

| Public pair | New bytes | ReduLink fixed | Secure ReduLink | Fixed-block sanity | Real rsync total | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| click-8.1.7-to-8.1.8 | 953,008 | 0.994x | 0.986x | 0.992x | 6.476x | rsync strongly better on this tree delta. |
| redis-7.2.4-to-7.2.5 | 15,533,278 | 0.998x | 0.990x | 0.996x | 73.135x | rsync strongly better on this tree delta. |
| nginx-1.25.3-to-1.25.4 | 7,377,697 | 0.997x | 0.989x | 0.995x | 49.489x | rsync strongly better on this tree delta. |

Interpretation: the source-release corpus is a useful negative result for ReduLink and a positive result for rsync. ReduLink should not be framed as a delta-transfer replacement. Its stronger niche remains endpoint transport compatibility and workloads with stable byte-identical chunks.

## Positive Public Text Fixture

Source: `results/public_artifact_suite.csv`.

| Public pair | Method | Input bytes | Wire bytes | Multiplier | Interpretation |
|---|---|---:|---:|---:|---|
| nginx-changes | fixed-block-reuse:fixed | 828,922 | 11,362 | 72.956x | Public byte-stable text/version pair. |
| nginx-changes | redulink:cdc | 828,922 | 15,603 | 53.126x | Positive public ReduLink case, but small and text-specific. |

## Public-Corpus Coverage and Limits

| Corpus family | Current coverage | Scale | Positive cases | Negative/weak cases | Production trace? | Limitation |
|---|---|---:|---|---|---|---|
| Pinned public text/version pairs | Yes | 23 KB-829 KB | nginx, redis | cpython, linux-parameters, RFC pair | No | Small smoke-level public fixture. |
| Public source-release snapshots | Yes | 0.95 MB-15.53 MB updates | rsync positive; ReduLink none at fixed 4 KiB | Click, Redis, nginx | No | Source trees are external but not network traces. |
| OCI/container layers | Scripted only | 297 KB fixture | Generated positive | Not independently curated | No | Need public registry layer corpus. |
| Git packs | No | - | - | - | No | Need repository synchronization traces. |
| Package repository metadata | Scripted only | 366 KB fixture | None | Generated negative | No | Need real apt/npm/pypi metadata pairs. |
| VM/backup snapshots | Scripted only | 1 MB fixture | Generated positive | Not independently curated | No | Need public VM/snapshot-like corpus. |
| Structured log archives | Scripted only | 1.5 MB fixture | None | Generated negative | No | Need real log archive pairs. |

## Native aioquic Stream and Datagram Accounting

Source: `results/quic_flow_comparison.csv`. ReduLink messages are carried inside QUIC STREAM data; custom extension frames are not implemented. UDP payload bytes are observed by a local proxy. Approximate IPv4/UDP bytes add 28 bytes per datagram and exclude link-layer overhead.

| Method | Loss every | Input bytes | Stream payload bytes | Stream multiplier | UDP payload bytes | Approx IPv4/UDP bytes | Approx IPv4/UDP multiplier | Reconstruction |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| raw-quic-stream | 0 | 98,304 | 98,304 | 1.000x | 106,157 | 108,901 | 0.903x | OK |
| redulink-binary-quic-stream | 0 | 98,304 | 30,816 | 3.190x | 36,568 | 37,800 | 2.601x | OK |
| raw-quic-stream | 9 | 98,304 | 98,304 | 1.000x | 121,772 | 125,776 | 0.782x | OK |
| redulink-binary-quic-stream | 9 | 98,304 | 30,816 | 3.190x | 39,809 | 41,265 | 2.382x | OK |

Interpretation: stream-payload accounting overstates the transport-level gain. The approximate IPv4/UDP multiplier is still positive for this controlled QUIC stream mapping, but full packet capture and netem/tc remain future work.

## Baseline Definitions

| Baseline | Definition | Caveat |
|---|---|---|
| Journal fixed-block reuse | Byte-scanning exact-block comparator with 16-byte match tokens and 20-byte literal-run overhead. | rsync-family approximation, not actual rsync. |
| External fixed-block sanity check | Exact 4096-byte block membership; 32-byte match token or 32-byte literal header per block. | Coarse sanity check in `run_real_workload_manifest.py`, not rolling rsync. |
| Real rsync baseline | `rsync -r -l -c --delete --no-whole-file --stats` against a temporary receiver copy. | Local content-oriented rsync run; reports rsync's own sent/received counters without archive-mode owner, group, permission, or timestamp metadata. |
| ReduLink fixed/CDC | FULL/REF representation-layer encoding with modeled overhead. | Not a production QUIC extension-frame encoding. |

## Fairness Evidence Ladder

| Evidence | File | Supports | Does not support |
|---|---|---|---|
| Wire-byte accounting | `results/wire_fairness_accounting.csv` | Bottleneck service should account encoded bytes, not reconstructed bytes. | Real QUIC congestion dynamics. |
| Concurrent localhost QUIC smoke | `results/quic_competing_flows.csv` | Overlapping raw and ReduLink aioquic transfers reconstruct correctly. | Controlled bottleneck fairness. |
| Local datagram accounting | `results/quic_flow_comparison.csv` | UDP payload and approximate IPv4/UDP byte accounting. | Full packet capture or real bottleneck queues. |
| Portable bottleneck emulation | `results/quic_bottleneck_emulation.csv` | Fluid fair-share model over measured stream payload bytes. | Kernel queueing, ACK pacing, loss coupling, packet capture. |
| Required next step | Not included | tc/netem or Mininet multi-flow experiments. | Current package cannot claim this. |

## Timing Scope

`wall_ms`, `throughput_mib_s_local`, and `runner_peak_kib` are local runner measurements. They are not line-rate performance claims. `cost_scope` distinguishes compression-only rows, fixed-block scans, ReduLink encode/decode rows, and composition diagnostics.
