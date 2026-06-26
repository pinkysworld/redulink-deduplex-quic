# Manuscript

Current submission title:

**ReduLink: Authenticated Redundancy-Suppressed Transmission for Effective Reconstructed Throughput over Encrypted WANs**

Scope subtitle:

**A representation-layer model and candidate Deduplex-QUIC profile**

## Status

- Protocol design: candidate profile, not production QUIC implementation.
- Artifact model: included as `src/redulink_model.py`.
- Backward-compatible wrapper: `src/redulink_proto_v0_5.py`.
- Unit/prototype tests: included and clean from a fresh checkout.
- Public fixture: pinned, checksum-verifiable, small text/version pairs.
- Target-class suite: deterministic generated warm/update fixtures with positive, weak, and negative cases.
- Evidence tables: generated from CSV by `scripts/summarize_benchmark_evidence.py`.
- Figures: generated from CSV by `scripts/plot_results.py` and `scripts/plot_warm_update_summary.py`.
- Production-scale QUIC validation: pending.

## Files

```text
paper/submission/ReduLink_full_draft_v0_9_submission_ready.docx
paper/submission/ReduLink_full_draft_v0_9_submission_ready.pdf
paper/evidence_tables.md
results/target_class_suite.csv
results/target_class_warm_update_summary.csv
results/public_artifact_suite.csv
results/synthetic_suite.csv
figures/target_class/redulink_vs_baseline_warm_update.png
docs/protocol_summary.md
docs/threat_model.md
```

## Claim Language To Preserve

ReduLink is not a faster physical link, a universal accelerator, a compression replacement, a delta-transfer replacement, or a completed QUIC implementation. The contribution is a scoped protocol model for authenticated reference substitution in cooperative endpoints, with explicit reconstruction invariants, miss repair, dictionary privacy boundaries, expansion limits, and reproducible evidence showing both useful and weak target classes.

## Evaluation Framing

The central evidence table should be the target-class evidence matrix, not the older synthetic multiplier table. The strongest empirical claim is narrow:

> ReduLink helps when byte-identical chunks survive across warm dictionary state and chunk boundaries. It is especially strong for aligned/page-like backup or VM workloads and selectively useful for some versioned artifacts, but it is not generally effective for all software updates, container layers, logs, or related text.

The public fixture is a pinned smoke/credibility fixture, not production trace validation. Larger public corpora remain needed for OCI layers, git packs, package metadata, VM/backup snapshots, and structured log archives.
