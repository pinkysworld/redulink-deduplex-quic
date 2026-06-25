# v0.8 Evidence Tables

These tables are generated from repository CSV outputs and are intended for the
manuscript or supplement. They separate evidence levels, avoid claiming a real
rsync implementation, and report local cost columns beside byte-savings results.

## Evidence Levels

| Level | What it supports | Current repository artifact |
|---|---|---|
| Analytic model | Explains when effective reconstructed throughput can exceed physical wire throughput. | Bandwidth model and conservative frame overheads. |
| Simulator | Validates FULL/REF reconstruction, negative controls, miss fallback, and byte accounting. | `src/redulink_proto_v0_5.py` plus `tests/`. |
| Controlled synthetic | Exercises repeat-heavy logs, update-like insertions, and mixed redundant/random data. | `results/synthetic_suite.csv`. |
| Frozen public fixture | Checks pinned public version pairs with URLs, SHA256s, byte sizes, and license notes. | `benchmarks/public_artifacts_manifest.csv` and `results/public_artifact_suite.csv`. |
| Prototype | Demonstrates endpoint cooperation and byte-exact reconstruction over localhost TCP. | `prototypes/redulink_socket_prototype.py`. |

## Synthetic Baseline Excerpt

Source: `results/synthetic_suite.csv`. Cost columns are local wall-clock
measurements from the runner that generated the CSV and are not
machine-independent constants.

| Workload | Method | Chunker | Input bytes | Wire bytes | Savings | Multiplier | CPU ms | MiB/s |
|---|---|---|---:|---:|---:|---:|---:|---:|
| logs | fixed-block-reuse | fixed | 2,578,182 | 35,466 | 0.986 | 72.694 | 11.113 | 221.249 |
| logs | ReduLink | fixed | 2,578,182 | 40,518 | 0.984 | 63.631 | 7.666 | 320.725 |
| logs | zstd-then-ReduLink | cdc | 66,540 | 11,182 | 0.832 | 5.951 | 50.472 | 1.257 |
| updates | fixed-block-reuse | fixed | 2,575,182 | 40,682 | 0.984 | 63.300 | 19.990 | 122.858 |
| updates | ReduLink | fixed | 2,575,182 | 1,314,222 | 0.490 | 1.959 | 10.007 | 245.412 |
| mixed | fixed-block-reuse | fixed | 3,187,727 | 645,011 | 0.798 | 4.942 | 208.353 | 14.591 |
| mixed | ReduLink | fixed | 3,187,727 | 651,863 | 0.796 | 4.890 | 8.735 | 348.038 |
| mixed | ReduLink | cdc | 3,187,727 | 667,559 | 0.791 | 4.775 | 1,899.219 | 1.601 |

Interpretation: the fixed-block reuse approximation is deliberately strong for
update-like byte streams and should be treated as a serious delta-transfer
comparator, not as the real rsync protocol. ReduLink's narrower claim is
authenticated endpoint-controlled references under transport dictionary state,
not dominance over compression or delta transfer on every workload.

## Frozen Public-Corpora Fixture

Source: `results/public_artifact_suite.csv` and
`benchmarks/public_artifacts_manifest.csv`.

| Artifact | Public source | Mode | Method | Multiplier | Savings | CPU ms | MiB/s |
|---|---|---|---|---:|---:|---:|---:|
| cpython-http-server | CPython v3.11.0 -> v3.12.0 `Lib/http/server.py` | changed version pair | fixed-block-reuse | 1.201 | 0.168 | 14.565 | 3.177 |
| cpython-http-server | CPython v3.11.0 -> v3.12.0 `Lib/http/server.py` | changed version pair | ReduLink CDC | 0.998 | 0.000 | 48.086 | 0.962 |
| cpython-pathlib | CPython v3.11.0 -> v3.12.0 `Lib/pathlib.py` | changed version pair | ReduLink CDC | 0.997 | 0.000 | 52.447 | 0.930 |
| linux-kernel-parameters | Linux v6.8 -> v6.9 kernel parameters documentation | changed version pair | ReduLink CDC | 0.998 | 0.000 | 258.930 | 1.004 |
| nginx-changes | nginx release-1.25.0 -> release-1.25.1 `changes.xml` | changed version pair | fixed-block-reuse | 72.956 | 0.986 | 3.295 | 239.894 |
| nginx-changes | nginx release-1.25.0 -> release-1.25.1 `changes.xml` | changed version pair | ReduLink CDC | 53.126 | 0.981 | 621.301 | 1.272 |
| redis-readme | Redis 7.2 -> 7.4 `README.md` | changed version pair | ReduLink CDC | 1.565 | 0.361 | 18.408 | 1.235 |
| ietf-quic-rfc | RFC 9000 -> RFC 9001 related QUIC texts | related public texts | ReduLink CDC | 0.998 | 0.000 | 244.857 | 0.491 |

Interpretation: the public fixture is still small and should not be framed as
production trace validation. Its value is that all rows are pinned, checksummed,
and reviewer-runnable. It now includes a real positive changed-version case
(`nginx-changes`), a modest case (`redis-readme`), and several negative or weak
changed-version cases where chunk identity is low. The Linux kernel parameters
and RFC rows show why the mechanism must be workload-gated: related text does
not automatically imply repeated chunk identity after the chosen chunking and
framing overheads.

## Selected Earlier Artifact Results

Source: `results/paper_real_artifact_cdc_selected.csv`. These rows are retained
as earlier controlled artifact measurements, not as production trace validation.

| Artifact | Mode | Input bytes | Wire-model bytes | Savings | Multiplier | Full | Ref |
|---|---|---:|---:|---:|---:|---:|---:|
| python-stdlib-py | cold-intra-artifact | 2,088,013 | 2,056,749 | 0.015 | 1.015 | 280 | 6 |
| python-stdlib-py | warm-update-like | 1,803,998 | 667,016 | 0.630 | 2.705 | 73 | 172 |
| dpkg-metadata | cold-intra-artifact | 2,084,976 | 2,092,132 | 0.000 | 0.997 | 298 | 0 |
| dpkg-metadata | warm-update-like | 2,002,495 | 805,404 | 0.598 | 2.486 | 86 | 201 |
| etc-config-text | warm-update-like | 1,315,817 | 597,539 | 0.546 | 2.202 | 102 | 132 |
| random-negative-control | cold-intra-artifact | 8,388,608 | 8,413,120 | 0.000 | 0.997 | 1024 | 0 |

Interpretation: warm dictionary state can produce effective multipliers on
repeated text-like artifacts while the random negative control remains below 1x
after frame overhead. These rows should be secondary to the frozen public
fixture and larger future corpora.
