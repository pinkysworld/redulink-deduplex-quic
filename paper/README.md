# Manuscript

This repository accompanies the v0.5 draft:

**ReduLink / Deduplex-QUIC: Authenticated Redundancy-Suppressed Transmission for Effective Bandwidth Expansion over Encrypted WANs**

The repository contains the runnable model, selected measurements, citation metadata, and a compact protocol summary.

```text
src/redulink_proto_v0_5.py
tests/
benchmarks/
scripts/plot_results.py
results/paper_real_artifact_cdc_selected.csv
results/synthetic_suite.csv
results/public_artifact_suite.csv
docs/protocol_summary.md
docs/threat_model.md
paper/evidence_tables.md
prototypes/redulink_socket_prototype.py
```

## Status

- Protocol design: v0.5
- Encoder/decoder model: included
- Selected artifact measurements: included
- Small fetched public-corpora benchmark: included
- Paper-facing evidence tables: included
- rsync-style rolling block reuse baseline: included
- Minimal socket prototype: included
- Baseline comparison runner: included
- Reproducible synthetic benchmark suite: included
- Public-artifact benchmark hook: included
- Figure generation from benchmark CSV: included
- GitHub Actions test workflow: included
- Random-data control: supported by script
- Production-scale trace validation: pending

## Strengthening changes for the manuscript

The next manuscript revision should emphasize six concrete evidence upgrades now
represented in the repository:

1. Public corpora are first-class evaluation targets. The public-artifact
   benchmark command accepts reproducible artifact families such as OCI layers,
   Linux release tarballs, git pack snapshots, package metadata, structured
   logs, and backup or replication streams.
2. Baselines are explicit. The benchmark CSVs compare raw bytes, gzip, zstd when
   available, ReduLink fixed chunking, ReduLink CDC, gzip-before-ReduLink,
   zstd-before-ReduLink when available, and ReduLink-before-gzip on the modeled
   frame stream.
3. Robustness is testable. Unit tests cover byte-exact reconstruction, random
   negative controls, warm-dictionary gains, safe reference-miss failure, and
   both chunkers. GitHub Actions runs the suite automatically.
4. Reproduction has one-command entry points. `benchmarks/run_synthetic_suite.sh`
   and `benchmarks/run_public_artifacts.sh` produce CSV files for tables.
5. Figures are generated from CSV, not manually drawn. `scripts/plot_results.py`
   emits effective-multiplier and savings plots plus a compact summary.
6. The protocol appendix is more implementation-oriented. The protocol summary
   now uses RFC-style terminology, frame definitions, sender/receiver behavior,
   dictionary policy, failure handling, security requirements, congestion and
   flow-control accounting, and failure cases.

The strongest next paper edit is to embed the compact tables from
`paper/evidence_tables.md` directly in Section 9. The tables provide concrete
compression-composition numbers and selected artifact results so the evidence
revision does not read as only a set of future benchmark commands.

Suggested claim language for the paper:

> We evaluate ReduLink on controlled synthetic workloads and provide
> reproducible commands for public artifact families. The model is checked by
> automated reconstruction and failure tests, and its evaluation compares raw
> transfer, conventional compression, rsync-style block reuse, ReduLink fixed
> chunking, ReduLink CDC, and compression/ReduLink composition cases.

Security scope language to retain:

> The Python artifact is a reconstruction and accounting model, not a production
> QUIC implementation. Cryptographic authentication, replay windows, 0-RTT
> policy, and cross-tenant dictionary controls are protocol requirements and are
> not claimed as implemented by the simulator.

## Additional evaluation targets

Future runs should cover larger public corpora:

- OCI/container layers
- git pack files
- Linux package repositories
- VM snapshots
- backup streams
- structured log archives
