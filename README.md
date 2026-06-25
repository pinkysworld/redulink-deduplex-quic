# ReduLink / Deduplex-QUIC

Authenticated redundancy-suppressed transmission for effective bandwidth expansion over encrypted WANs.

ReduLink studies how cooperative endpoints can reduce transmitted bytes by replacing repeated payload chunks with compact authenticated references. The design targets workloads with visible redundancy, such as software updates, container layers, structured logs, backups, and replication streams.

The mechanism does not change the physical link rate. It improves effective reconstructed payload throughput when repeated content can be represented safely by references under endpoint-controlled dictionary state.

## Repository contents

```text
src/redulink_proto_v0_5.py                         Encoder/decoder model
tests/                                             Reconstruction and safety tests
benchmarks/                                        Reproducible benchmark suites
prototypes/redulink_socket_prototype.py            Minimal socket prototype
scripts/plot_results.py                            Figure generation from CSV
results/paper_real_artifact_cdc_selected.csv       Selected v0.5 measurements
results/public_artifact_suite.csv                  Fetched public-corpora results
docs/protocol_summary.md                           Protocol summary
docs/threat_model.md                               Threat model and security scope
paper/README.md                                    Manuscript note
paper/evidence_tables.md                           Paper-facing result excerpts
.github/workflows/tests.yml                        CI test workflow
LICENSE
CITATION.cff
```

## Protocol sketch

ReduLink uses four logical frame types:

```text
FULL(epoch, stream_id, offset, chunk_id, payload, auth_tag)
REF(epoch, stream_id, offset, original_length, chunk_id, nonce, auth_tag)
MISS(epoch, stream_id, offset, chunk_id)
DICT_ACK(epoch, chunk_id)
```

FULL frames carry new chunks. REF frames identify chunks already available to the receiver. MISS frames request fallback when a reference cannot be resolved. DICT_ACK frames support conservative dictionary synchronization.

## Design rules

- Count congestion-controlled usage by transmitted wire bytes.
- Deliver reconstructed bytes only after dictionary, epoch, and authentication checks.
- Scope dictionaries by connection or trusted origin.
- Bound reference expansion to prevent abuse.
- Fall back to FULL transmission on unresolved references.
- Disable reference generation when the hit rate is too low.

## Run

Directory or file input:

```bash
python3 src/redulink_proto_v0_5.py artifact --path /path/to/data --chunker cdc --mode warm
```

Random-data negative control:

```bash
python3 src/redulink_proto_v0_5.py random --size-mib 8 --chunker cdc
```

Structured-log workload:

```bash
python3 src/redulink_proto_v0_5.py synthetic --variant logs --chunker fixed
```

The implementation uses only the Python standard library.

## Tests

```bash
python3 -m unittest discover -s tests
```

The tests verify byte-exact FULL/REF reconstruction, fixed and CDC chunkers,
random-data negative controls, warm-dictionary gains, safe failure on receiver
REF misses, FULL/REF length validation, miss-rate fallback behavior, and
wire-byte accounting. GitHub Actions runs these tests on push and pull request.

## Reproducible benchmarks

Synthetic benchmark suite:

```bash
bash benchmarks/run_synthetic_suite.sh
```

Public-artifact benchmark suite:

```bash
bash benchmarks/run_public_artifacts.sh \
  ubuntu-base=/path/to/oci/ubuntu-base-layers \
  linux-kernel=/path/to/linux-release-tarballs \
  git-pack=/path/to/git-pack-snapshots
```

The benchmark CSVs compare raw bytes, gzip, zstd when available, ReduLink fixed
chunking, ReduLink CDC, an rsync-style rolling block reuse baseline, and
compression/ReduLink composition cases. The public artifact runner accepts
manifest-based reproducible corpora rather than hiding large downloads inside
the script.

Fetch the small public-corpora fixture and run it:

```bash
python3 benchmarks/fetch_public_corpora.py
bash benchmarks/run_public_artifacts.sh --manifest benchmarks/public_artifacts_manifest.csv
```

Generate paper figures from any benchmark CSV:

```bash
python3 scripts/plot_results.py results/synthetic_suite.csv --output-dir figures
```

## Measurements

Selected v0.5 measurements are provided in:

```text
results/paper_real_artifact_cdc_selected.csv
results/synthetic_suite.csv
results/public_artifact_suite.csv
paper/evidence_tables.md
```

Warm/update-like runs show the largest gains because the receiver dictionary
already contains related prior data. Random-data controls are expected to show
no useful savings once reference overhead is included. ReduLink is not a
replacement for compression: compression primarily exploits redundancy inside
the current object or stream, while ReduLink suppresses repeated chunks across
connection, epoch, or update history under authenticated receiver-side
dictionary state.

## Security and implementation scope

The Python implementation is a throughput/reconstruction model. It does not
implement QUIC packetization, cryptographic authentication tags, replay windows,
0-RTT policy, production dictionary manifests, or cross-tenant privacy controls.
Those requirements are specified in `docs/protocol_summary.md` and scoped in
`docs/threat_model.md`.

## Prototype

The minimal socket prototype demonstrates endpoint cooperation over localhost:

```bash
python3 prototypes/redulink_socket_prototype.py demo
```

It sends modeled FULL/REF frames over a TCP socket and verifies byte-exact
receiver reconstruction. It is not a QUIC implementation.

## Manuscript

This repository accompanies the v0.5 draft:

**ReduLink / Deduplex-QUIC: Authenticated Redundancy-Suppressed Transmission for Effective Bandwidth Expansion over Encrypted WANs**

The current repository publishes the runnable model, selected measurements,
automated tests, reproducible benchmark commands, plot generation, citation
metadata, and protocol summary. Larger validation runs should use public corpora
such as OCI layers, git packs, package repositories, VM snapshots, structured
logs, and backup streams.

## Citation

Use `CITATION.cff`.

## License

The code is released under the MIT License. Manuscript text remains with the author unless separately licensed.
