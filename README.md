# ReduLink / Deduplex-QUIC

Authenticated redundancy-suppressed transmission for effective bandwidth expansion over encrypted WANs.

ReduLink studies how cooperative endpoints can reduce transmitted bytes by replacing repeated payload chunks with compact authenticated references. The design targets workloads with visible redundancy, such as software updates, container layers, structured logs, backups, and replication streams.

The mechanism does not change the physical link rate. It improves effective reconstructed payload throughput when repeated content can be represented safely by references under endpoint-controlled dictionary state.

## Repository contents

```text
src/redulink_proto_v0_5.py                         Encoder/decoder model
results/paper_real_artifact_cdc_selected.csv       Selected v0.5 measurements
docs/protocol_summary.md                           Protocol summary
paper/README.md                                    Manuscript note
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

## Measurements

Selected v0.5 measurements are provided in:

```text
results/paper_real_artifact_cdc_selected.csv
```

Warm/update-like runs show the largest gains because the receiver dictionary already contains related prior data. Random-data controls are expected to show no useful savings once reference overhead is included.

## Manuscript

This repository accompanies the v0.5 draft:

**ReduLink / Deduplex-QUIC: Authenticated Redundancy-Suppressed Transmission for Effective Bandwidth Expansion over Encrypted WANs**

The current repository publishes the runnable model, selected measurements, citation metadata, and protocol summary. Larger validation runs should use public corpora such as OCI layers, git packs, package repositories, VM snapshots, structured logs, and backup streams.

## Citation

Use `CITATION.cff`.

## License

The code is released under the MIT License. Manuscript text remains with the author unless separately licensed.
