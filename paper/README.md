# Manuscript status

This repository corresponds to the v0.5 research draft:

**ReduLink / Deduplex-QUIC: Authenticated Redundancy-Suppressed Transmission for Effective Bandwidth Expansion over Encrypted WANs**

The public repository currently contains the runnable artifact, selected results, citation metadata, and a compact protocol summary.

The full DOCX/PDF manuscript can be attached as a GitHub release artifact or uploaded manually. The core artifact needed to reproduce the current proof-of-concept behavior is in:

```text
src/redulink_proto_v0_5.py
results/paper_real_artifact_cdc_selected.csv
docs/protocol_summary.md
```

## Current evidence level

- Conceptual protocol design: v0.5
- Minimal encoder/decoder prototype: included
- Selected real-artifact sanity experiments: included
- Negative random-data control: supported by script
- Production trace validation: not yet included

## Recommended next step

Run the prototype on larger public corpora, especially:

- OCI/container layers
- git pack files
- Linux package repositories
- VM snapshots
- backup streams
- structured log archives
