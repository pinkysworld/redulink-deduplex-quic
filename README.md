# ReduLink / Deduplex-QUIC

**Authenticated redundancy-suppressed transmission for effective bandwidth expansion over encrypted WANs.**

ReduLink is a research prototype and manuscript artifact exploring how cooperative endpoints can increase **effective reconstructed payload throughput** without increasing the physical line rate. The core mechanism replaces repeated payload chunks with compact authenticated references bound to short-lived epoch dictionaries.

ReduLink is **not** faster Ethernet and does not claim to increase the physical line rate. It is a protocol design for **semantic bandwidth multiplication** when real redundancy exists in endpoint-visible traffic.

## Repository contents

```text
src/redulink_proto_v0_5.py                         Minimal encoder/decoder prototype
results/paper_real_artifact_cdc_selected.csv       Selected v0.5 artifact results
docs/protocol_summary.md                           Compact protocol and evaluation summary
paper/README.md                                    Manuscript status note
LICENSE
CITATION.cff
```

## Core idea

ReduLink replaces repeated payload chunks with authenticated references:

```text
FULL(epoch, stream_id, offset, chunk_id, payload, auth_tag)
REF(epoch, stream_id, offset, original_length, chunk_id, nonce, auth_tag)
MISS(epoch, stream_id, offset, chunk_id)
DICT_ACK(epoch, chunk_id)
```

The receiver reconstructs the original byte stream only when the reference is valid under the current endpoint-controlled dictionary state. If a reference cannot be resolved, the sender falls back to full transmission.

## Design principles

- Physical line rate is never exceeded.
- Effective reconstructed payload throughput can exceed line rate for redundant workloads.
- Congestion accounting is based on transmitted wire bytes, not reconstructed bytes.
- Dictionaries are epoch-scoped and privacy-scoped.
- Per-connection dictionaries are the default.
- Reference misses trigger safe fallback.
- Expansion is bounded to prevent abuse.
- Random, compressed, or hidden encrypted traffic should receive little or no benefit.

## Quick start

Run the prototype on a file or directory:

```bash
python3 src/redulink_proto_v0_5.py artifact --path /path/to/artifacts --chunker cdc --mode warm
```

Run a negative control:

```bash
python3 src/redulink_proto_v0_5.py random --size-mib 8 --chunker cdc
```

Run a synthetic structured-log workload:

```bash
python3 src/redulink_proto_v0_5.py synthetic --variant logs --chunker fixed
```

The script is intentionally standard-library-only.

## Example selected v0.5 results

The included CSV reports selected real-artifact sanity experiments. The strongest gains appear in warm/update-like settings, where a receiver dictionary already contains prior related artifacts. Negative controls should show near-zero or negative benefit once reference overhead is counted.

```text
results/paper_real_artifact_cdc_selected.csv
```

## Manuscript status

This repository corresponds to the v0.5 manuscript draft:

**ReduLink / Deduplex-QUIC: Authenticated Redundancy-Suppressed Transmission for Effective Bandwidth Expansion over Encrypted WANs**

The repository currently publishes the runnable artifact, selected data, citation metadata, and protocol summary. The full DOCX/PDF manuscript draft can be attached separately as a release artifact or uploaded manually if desired.

The evaluation should be interpreted as a reproducible proof of concept, not as production trace validation. The next intended step is testing larger public corpora such as OCI/container layers, git packs, package repositories, VM snapshots, logs, and backup streams.

## Citation

Please cite using `CITATION.cff`.

## License

Prototype code is released under the MIT License. The manuscript text remains a research draft by the author unless separately licensed.
