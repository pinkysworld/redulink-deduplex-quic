# Manuscript

This repository accompanies the v0.5 draft:

**ReduLink / Deduplex-QUIC: Authenticated Redundancy-Suppressed Transmission for Effective Bandwidth Expansion over Encrypted WANs**

The repository contains the runnable model, selected measurements, citation metadata, and a compact protocol summary.

```text
src/redulink_proto_v0_5.py
results/paper_real_artifact_cdc_selected.csv
docs/protocol_summary.md
```

## Status

- Protocol design: v0.5
- Encoder/decoder model: included
- Selected artifact measurements: included
- Random-data control: supported by script
- Production-scale trace validation: pending

## Additional evaluation targets

Future runs should cover larger public corpora:

- OCI/container layers
- git pack files
- Linux package repositories
- VM snapshots
- backup streams
- structured log archives
