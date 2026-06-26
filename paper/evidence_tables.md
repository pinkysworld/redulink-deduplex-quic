# Version 2.3 Evidence Tables

These tables summarize repository CSV outputs for the journal-ready package. They emphasize evidence level, raw byte context, wall-clock scope, negative controls, and the distinction between QUIC stream payload bytes and full packet bytes.

## Evidence Levels

| Level | What it supports | Current repository artifact |
|---|---|---|
| Representation model | FULL/REF byte reconstruction, accounting, miss failure. | `src/redulink_model.py`, `tests/`. |
| Controlled target fixtures | Target-class behavior under deterministic generated warm/update pairs. | `benchmarks/generate_target_corpora.py`, `results/target_class_suite.csv`. |
| Journal fixtures | Disk, OCI-like, package-metadata, repository, log, and compressed negative cases. | `benchmarks/generate_journal_corpora.py`, `results/journal_workload_suite.csv`. |
| Frozen public text fixture | Reviewer-runnable pinned public text/version pairs. | `benchmarks/public_artifacts_manifest.csv`, `results/public_artifact_suite.csv`. |
| External public source releases | Independently curated Click, Redis, and nginx release snapshots. | `benchmarks/fetch_external_public_corpora.py`, `benchmarks/external_public_manifest.csv`, `results/external_public_suite.csv`. |
| Native QUIC stream prototype | Endpoint cooperation over TLS-protected aioquic streams. | `prototypes/redulink_aioquic_experiment.py`, `results/quic_flow_comparison.csv`. |
| Pending transport validation | Custom QUIC extension frames, packet capture, tc/netem competing-flow fairness, migration, 0-RTT, exporter-derived keys. | Not implemented. |

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

Source: `benchmarks/external_public_manifest.csv` and `results/external_public_suite.csv`.

| Public pair | New bytes | ReduLink fixed | Secure ReduLink | Fixed-block reuse | Reconstruction | Interpretation |
|---|---:|---:|---:|---:|---|---|
| click-8.1.7-to-8.1.8 | 953,008 | 0.994x | 0.986x | 0.992x | OK | No useful gain; overhead exceeds saved references. |
| redis-7.2.4-to-7.2.5 | 15,533,278 | 0.998x | 0.990x | 0.996x | OK | No useful gain at fixed 4 KiB boundaries. |
| nginx-1.25.3-to-1.25.4 | 7,377,697 | 0.997x | 0.989x | 0.995x | OK | No useful gain at fixed 4 KiB boundaries. |

Interpretation: the external public corpus is a useful negative result. Ordinary related source-release trees are not automatically good ReduLink targets. This strengthens the conditional claim and motivates future public corpora for workloads where byte-stable chunks are expected, such as OCI layers, VM snapshots, or package repository artifacts.

## Public-Corpus Coverage and Limits

| Corpus family | Current coverage | Scale | Positive cases | Negative/weak cases | Production trace? | Limitation |
|---|---|---:|---|---|---|---|
| Pinned public text/version pairs | Yes | 23 KB-829 KB | nginx, redis | cpython, linux-parameters, RFC pair | No | Small smoke-level public fixture. |
| Public source-release snapshots | Yes | 0.95 MB-15.53 MB updates | None at fixed 4 KiB | Click, Redis, nginx | No | Source trees are external but not network traces. |
| OCI/container layers | Scripted only | 297 KB fixture | Generated positive | Not independently curated | No | Need public registry layer corpus. |
| Git packs | No | - | - | - | No | Need repository synchronization traces. |
| Package repository metadata | Scripted only | 366 KB fixture | None | Generated negative | No | Need real apt/npm/pypi metadata pairs. |
| VM/backup snapshots | Scripted only | 1 MB fixture | Generated positive | Not independently curated | No | Need public VM/snapshot-like corpus. |
| Structured log archives | Scripted only | 1.5 MB fixture | None | Generated negative | No | Need real log archive pairs. |

## Native aioquic Stream-Mapping Result

Source: `results/quic_flow_comparison.csv`. ReduLink messages are carried inside QUIC STREAM data; custom extension frames are not implemented.

| Method | Loss every | Input bytes | QUIC stream payload bytes | Effective stream-payload multiplier | Semantic misses | Repair FULL frames | Reconstruction |
|---|---:|---:|---:|---:|---:|---:|---|
| raw-quic-stream | 0 | 98,304 | 98,304 | 1.000x | 0 | 0 | OK |
| redulink-binary-quic-stream | 0 | 98,304 | 30,816 | 3.190x | 13 | 13 | OK |
| raw-quic-stream | 9 | 98,304 | 98,304 | 1.000x | 0 | 0 | OK |
| redulink-binary-quic-stream | 9 | 98,304 | 30,816 | 3.190x | 13 | 13 | OK |

The multiplier here is over QUIC stream payload bytes, not full UDP/IP/QUIC packet bytes. Packet capture remains future work.

## Fixed-Block Baseline Definition

| Parameter | Value |
|---|---|
| Default block size | 4096 bytes for the journal and external public suites unless overridden. |
| Match rule | Byte-scan exact block match using a prefix lookup followed by full-block equality. |
| Token overhead | 16 bytes per matched block reference. |
| Literal overhead | 20 bytes per literal run plus literal bytes. |
| Checksum exchange | Not modeled. |
| rsync compatibility | No; this is an rsync-family fixed-block reuse approximation, not the rsync protocol. |
| Compression order | None for fixed-block rows. |

## Fairness Evidence Ladder

| Evidence | File | Supports | Does not support |
|---|---|---|---|
| Wire-byte accounting | `results/wire_fairness_accounting.csv` | Bottleneck service should account encoded bytes, not reconstructed bytes. | Real QUIC congestion dynamics. |
| Concurrent localhost QUIC smoke | `results/quic_competing_flows.csv` | Overlapping raw and ReduLink aioquic transfers reconstruct correctly. | Controlled bottleneck fairness. |
| Portable bottleneck emulation | `results/quic_bottleneck_emulation.csv` | Fluid fair-share model over measured stream payload bytes. | Kernel queueing, ACK pacing, loss coupling, packet capture. |
| Required next step | Not included | tc/netem or Mininet multi-flow experiments. | Current package cannot claim this. |

## Timing Scope

`wall_ms`, `throughput_mib_s_local`, and `runner_peak_kib` are local runner measurements. They are not line-rate performance claims. `cost_scope` distinguishes compression-only rows, fixed-block scans, ReduLink encode/decode rows, and composition diagnostics.
