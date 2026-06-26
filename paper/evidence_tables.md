# v0.9 Evidence Tables

These tables are generated from repository CSV outputs. They emphasize evidence level, raw byte context, wall-clock cost scope, and negative controls.

## Evidence Levels

| Level | What it supports | Current repository artifact |
|---|---|---|
| Representation model | FULL/REF byte reconstruction, accounting, miss failure. | `src/redulink_model.py`, `tests/`. |
| Controlled target fixtures | Target-class behavior under deterministic generated warm/update pairs. | `benchmarks/generate_target_corpora.py`, `results/target_class_suite.csv`. |
| Frozen public fixture | Reviewer-runnable pinned public text/version pairs. | `benchmarks/public_artifacts_manifest.csv`, `results/public_artifact_suite.csv`. |
| Prototype | Endpoint cooperation over localhost TCP. | `prototypes/redulink_socket_prototype.py`. |
| Pending transport validation | Real QUIC loss, flow control, congestion fairness, migration, 0-RTT. | Not implemented. |

## Target-Class Evidence Matrix

Source: `results/target_class_suite.csv` and `results/target_class_warm_update_summary.csv`. These are controlled generated fixtures, not production traces.

| Target | Input bytes | Warm bytes | Changed bytes | Best compression | Fixed-block | ReduLink fixed | ReduLink CDC | Interpretation |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| software update | 515,534 | 478,034 | 292,158 | zstd-3 11.958x | 1.000x | 0.997x | 0.999x | ReduLink loses; single-object compression dominates this generated update shape. |
| container layer | 624,778 | 493,423 | 600,951 | zstd-3 4.087x | 1.799x | 1.010x | 0.999x | Weak reference identity; fixed-block baseline helps more than ReduLink. |
| git-packlike | 1,038,009 | 973,109 | 660,483 | zstd-3 18.080x | 1.269x | 1.082x | 1.193x | Modest warm-dictionary gain, especially with CDC. |
| VM backup | 3,686,400 | 3,686,400 | 49,623 | zstd-3 9.949x | 21.560x | 20.701x | 2.771x | Strong for aligned/page-like state; fixed-block and ReduLink fixed both benefit. |
| structured logs | 4,980,940 | 4,075,370 | 906,941 | gzip-6 12.397x | 1.070x | 1.067x | 0.999x | Compression dominates; reference substitution is weak after overhead. |
| random negative | 2,097,152 | 2,097,152 | 2,088,982 | zstd-3 1.000x | 1.000x | 0.997x | 0.998x | Correct no-gain random control. |
| compressed related | 382,339 | 382,242 | 29,416 | zstd-3 2.192x | 12.417x | 12.117x | 9.623x | Diagnostic positive: related compressed streams retain reusable byte regions. |
| compressed negative | 786,678 | 786,678 | 783,669 | zstd-3 1.000x | 1.000x | 0.997x | 0.998x | Correct no-gain compressed negative control. |

Interpretation: ReduLink helps only when byte-identical chunks survive across warm dictionary state and chosen chunk boundaries. The target-class suite deliberately includes weak and negative cases, because related data does not automatically imply referenceable chunk identity.

## Public-Corpus Coverage and Limits

| Corpus family | Current fixture | Scale | Positive cases | Negative/weak cases | Production trace? | Limitation |
|---|---|---:|---|---|---|---|
| Text version pairs | Yes | 23 KB-829 KB | nginx, redis | cpython, linux-parameters, RFC pair | No | Small, text-only, smoke-level public fixture. |
| OCI/container layers | No | - | - | - | No | Needed for claimed container workloads. |
| Git packs | No | - | - | - | No | Needed for repository synchronization claims. |
| Package repository metadata | No | - | - | - | No | Needed for software-update claims. |
| VM/backup snapshots | No | - | - | - | No | Needed beyond generated sparse-block fixture. |
| Structured log archives | No | - | - | - | No | Needed beyond generated log fixture. |

## Frozen Public-Corpora Fixture Excerpt

Source: `results/public_artifact_suite.csv` and `benchmarks/public_artifacts_manifest.csv`.

| Artifact | Method | Input bytes | Warm bytes | Changed bytes | Wire bytes | Multiplier | Wall ms | MiB/s local |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| nginx-changes | fixed-block-reuse:fixed | 828,922 | 827,855 | 797,468 | 11,362 | 72.956x | 1.730 | 456.982 |
| nginx-changes | redulink:cdc | 828,922 | 827,855 | 797,468 | 15,603 | 53.126x | 319.241 | 2.476 |
| redis-readme | redulink:cdc | 23,845 | 22,607 | 22,354 | 15,236 | 1.565x | 7.901 | 2.878 |
| cpython-http-server | redulink:cdc | 48,516 | 47,735 | 40,101 | 48,612 | 0.998x | 17.897 | 2.585 |
| linux-kernel-parameters | redulink:cdc | 272,692 | 269,275 | 259,568 | 273,364 | 0.998x | 98.707 | 2.635 |
| ietf-quic-rfc | redulink:cdc | 126,175 | 403,442 | 393,620 | 126,487 | 0.998x | 113.117 | 1.064 |

Interpretation: the public fixture is intentionally small but pinned and checksum-verifiable. It contains one strong public changed-version case, one modest positive case, and several weak cases.

## Synthetic Excerpt

Synthetic rows are retained as mechanism checks and should not be read as production trace validation.

| Workload | Method | Input bytes | Wire bytes | Multiplier | Wall ms | MiB/s local |
|---|---|---:|---:|---:|---:|---:|
| logs | redulink:fixed | 2,578,182 | 40,518 | 63.631x | 4.034 | 609.569 |
| logs | redulink:cdc | 2,578,182 | 57,558 | 44.793x | 944.324 | 2.604 |
| updates | redulink:fixed | 2,575,182 | 1,314,222 | 1.959x | 4.725 | 519.769 |
| mixed | redulink:fixed | 3,187,727 | 651,863 | 4.890x | 4.406 | 689.980 |
| mixed | redulink:cdc | 3,187,727 | 667,559 | 4.775x | 1017.794 | 2.987 |

## Fixed-Block Baseline Definition

| Parameter | Value |
|---|---|
| Default block size | 8192 bytes unless `--chunk-size` overrides it. |
| Match rule | Byte-scan exact block match using a prefix lookup followed by full-block equality. |
| Token overhead | 16 bytes per matched block reference. |
| Literal overhead | 20 bytes per literal run plus literal bytes. |
| Checksum exchange | Not modeled. |
| rsync compatibility | No; this is an rsync-family fixed-block reuse approximation, not the rsync protocol. |
| Compression order | None for fixed-block rows. |

## Timing Scope

`wall_ms`, `throughput_mib_s_local`, and `runner_peak_kib` are local runner measurements. They are not line-rate performance claims. `cost_scope` distinguishes compression-only rows, fixed-block scans, ReduLink encode/decode rows, and composition diagnostics.
