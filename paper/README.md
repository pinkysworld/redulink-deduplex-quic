# Manuscript

Current submission title:

**ReduLink: Authenticated Reference Substitution for Redundancy-Suppressed Transfers over Encrypted QUIC Streams**

## Status

- Protocol design: scoped endpoint representation layer over encrypted QUIC streams.
- Current implementation: native aioquic stream mapping with compact binary FULL, REF, MISS, and repair messages.
- Custom Deduplex-QUIC extension frames: future work.
- Artifact model: `src/redulink_model.py`.
- Authenticated model and key schedule: `src/redulink_secure.py`, `src/redulink_key_schedule.py`.
- Native QUIC prototype: `prototypes/redulink_aioquic_experiment.py`.
- Deterministic journal fixtures: `benchmarks/generate_journal_corpora.py`, `results/journal_workload_suite.csv`.
- External public source-release suite: `benchmarks/fetch_external_public_corpora.py`, `results/external_public_suite.csv`.
- Evidence tables: `paper/evidence_tables.md`.
- Manuscript builder: `scripts/build_manuscript_v2_3.py`.

## Files

```text
paper/submission/ReduLink_journal_ready_v2_3.docx
paper/submission/ReduLink_journal_ready_v2_3.pdf
paper/evidence_tables.md
results/journal_workload_suite.csv
results/external_public_suite.csv
results/quic_flow_comparison.csv
results/quic_competing_flows.csv
results/quic_bottleneck_emulation.csv
docs/protocol_summary.md
docs/threat_model.md
docs/reference_audit.md
docs/internal_peer_review_v2_2.md
```

## Claim Language To Preserve

ReduLink is not a faster physical link, a universal accelerator, a compression replacement, a full rsync/zsync replacement, or a completed custom QUIC extension implementation. The contribution is a scoped protocol model and artifact for authenticated reference substitution in cooperative endpoints, with explicit reconstruction invariants, miss repair, dictionary privacy boundaries, expansion limits, and reproducible evidence showing both useful and weak workload classes.

The strongest empirical claim is narrow:

> ReduLink helps when byte-identical chunks survive across warm dictionary state and chunk boundaries. It is strong for aligned/page-like state and selected versioned artifacts, but it is not generally effective for all software updates, source releases, container layers, logs, or related text.

## Current Additions

This package adds a longer journal manuscript, an external public source-release corpus from Click, Redis, and nginx, a reproducible manuscript builder, explicit stream-payload versus packet-byte accounting language, expanded related work, expanded security/privacy discussion, and a clearer fairness evidence ladder.
