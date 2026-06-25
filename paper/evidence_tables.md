# v0.5 Evidence Tables

These tables are generated from repository CSV outputs and are intended for the
manuscript or supplement. They address the reviewer request for concrete
numbers, public-corpora evidence, and a closer file-transfer baseline.

## Compression, rsync, and ReduLink Baseline Excerpt

Source: `results/synthetic_suite.csv`.

| Workload | Mode | Method | Chunker | Input bytes | Wire bytes | Savings | Multiplier |
|---|---|---|---:|---:|---:|---:|---:|
| logs | single-object | raw | none | 2,578,182 | 2,578,182 | 0.000 | 1.000 |
| logs | single-object | gzip-6 | none | 2,578,182 | 145,905 | 0.943 | 17.670 |
| logs | single-object | zstd-3 | none | 2,578,182 | 66,540 | 0.974 | 38.746 |
| logs | warm-update-like | rsync-block-reuse | fixed | 2,578,182 | 35,466 | 0.986 | 72.694 |
| logs | warm-update-like | redulink | fixed | 2,578,182 | 40,518 | 0.984 | 63.631 |
| logs | warm-update-like | redulink | cdc | 2,578,182 | 57,558 | 0.978 | 44.793 |
| logs | warm-update-like | zstd-then-redulink | cdc | 66,540 | 11,182 | 0.832 | 5.951 |
| updates | single-object | zstd-3 | none | 2,575,182 | 66,633 | 0.974 | 38.647 |
| updates | warm-update-like | rsync-block-reuse | fixed | 2,575,182 | 40,682 | 0.984 | 63.300 |
| updates | warm-update-like | redulink | fixed | 2,575,182 | 1,314,222 | 0.490 | 1.959 |
| updates | warm-update-like | redulink | cdc | 2,575,182 | 1,332,198 | 0.483 | 1.933 |
| updates | warm-update-like | zstd-then-redulink | cdc | 66,633 | 38,964 | 0.415 | 1.710 |
| mixed | single-object | zstd-3 | none | 3,187,727 | 66,840 | 0.979 | 47.692 |
| mixed | warm-update-like | rsync-block-reuse | fixed | 3,187,727 | 644,999 | 0.798 | 4.942 |
| mixed | warm-update-like | redulink | fixed | 3,187,727 | 651,863 | 0.796 | 4.890 |
| mixed | warm-update-like | redulink | cdc | 3,187,727 | 667,559 | 0.791 | 4.775 |
| mixed | warm-update-like | zstd-then-redulink | cdc | 66,840 | 11,482 | 0.828 | 5.821 |

Interpretation: conventional compression remains a strong single-object
baseline. The rsync-style baseline is deliberately strong for update-like byte
streams and should be treated as a serious file-transfer comparator. ReduLink's
separate claim is transport-adjacent authenticated references under endpoint
dictionary state, not dominance over rsync on every file-delta workload.

## Small Public-Corpora Fixture

Source: `results/public_artifact_suite.csv` and
`benchmarks/public_artifacts_manifest.csv`.

| Artifact | Public source | Mode | Method | Multiplier | Savings |
|---|---|---|---:|---:|---:|
| cpython-http-server | CPython v3.12.0 -> v3.12.1 `Lib/http/server.py` | warm update | rsync-block-reuse | 3.050 | 0.672 |
| cpython-http-server | CPython v3.12.0 -> v3.12.1 `Lib/http/server.py` | warm update | ReduLink CDC | 11.437 | 0.913 |
| linux-kernel-parameters | Linux v6.8 -> v6.9 kernel parameters documentation | warm update | rsync-block-reuse | 1.031 | 0.030 |
| linux-kernel-parameters | Linux v6.8 -> v6.9 kernel parameters documentation | warm update | ReduLink CDC | 0.997 | 0.000 |
| ietf-quic-rfc | RFC 9000 -> RFC 9001 related QUIC texts | warm related | rsync-block-reuse | 1.000 | 0.000 |
| ietf-quic-rfc | RFC 9000 -> RFC 9001 related QUIC texts | warm related | ReduLink CDC | 0.998 | 0.000 |

Interpretation: this fixture is intentionally small and reproducible. It should
not be presented as production trace validation. It is useful because it
includes both a positive public version-pair case and negative/weak cases where
neither ReduLink nor rsync-style reuse finds much repeated chunk identity.

## Selected Artifact Results

Source: `results/paper_real_artifact_cdc_selected.csv`.

| Artifact | Mode | Input bytes | Wire-model bytes | Savings | Multiplier | Full | Ref |
|---|---|---:|---:|---:|---:|---:|---:|
| python-stdlib-py | cold-intra-artifact | 2,088,013 | 2,056,749 | 0.015 | 1.015 | 280 | 6 |
| python-stdlib-py | warm-update-like | 1,803,998 | 667,016 | 0.630 | 2.705 | 73 | 172 |
| dpkg-metadata | cold-intra-artifact | 2,084,976 | 2,092,132 | 0.000 | 0.997 | 298 | 0 |
| dpkg-metadata | warm-update-like | 2,002,495 | 805,404 | 0.598 | 2.486 | 86 | 201 |
| etc-config-text | cold-intra-artifact | 1,537,744 | 1,530,934 | 0.004 | 1.004 | 275 | 3 |
| etc-config-text | warm-update-like | 1,315,817 | 597,539 | 0.546 | 2.202 | 102 | 132 |
| random-negative-control | cold-intra-artifact | 8,388,608 | 8,413,120 | 0.000 | 0.997 | 1024 | 0 |

Interpretation: these selected artifact results are still small-scale and should
not be framed as production trace validation. They are useful evidence that warm
dictionary state can produce 2.2x to 2.7x effective multipliers on repeated
text-like artifacts while the random negative control remains below 1x after
frame overhead.
