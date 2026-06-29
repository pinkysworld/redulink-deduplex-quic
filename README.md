# ReduLink journal-ready package v3.0

This package contains the ReduLink manuscript and reproducibility artifact for an applied networking/systems journal submission.

## Main manuscript

- DOCX: `paper/submission/ReduLink_journal_ready_v3_0.docx`
- PDF: `paper/submission/ReduLink_journal_ready_v3_0.pdf`
- Build source: `scripts/build_manuscript_v3_0.py` (figures: `scripts/make_journal_figures_v2_8.py`)

## Claim boundary

ReduLink is authenticated, scoped, QUIC-compatible reference substitution for selected warm-state transfers. It is not a new matching algorithm, not a universal accelerator, not a replacement for compression or rsync, and not a custom QUIC extension-frame implementation. The native QUIC artifact maps compact binary ReduLink records into encrypted aioquic streams.

## What is implemented

- Authenticated FULL/REF/MISS-style reference substitution model.
- Compact binary ReduLink stream messages over native aioquic QUIC streams.
- Exporter-style HKDF key schedule model for context separation.
- Tamper, replay, wrong-scope, wrong-epoch, wrong-stream, wrong-offset, and wrong-length tests.
- Deterministic journal fixtures, public source-release negative pairs, object-aligned public release workloads, and one Redis-derived layer-like public positive workload.
- Real rsync baselines, compression baselines, block-size sensitivity, repeated QUIC trials, component-cost measurements, and conservative accounting-layer separation.

## Validation commands

Fast reviewer smoke validation:

```bash
python3 scripts/run_smoke_validation.py
```

Full validation:

```bash
python3 scripts/run_full_validation.py
```

The full suite includes integration and aioquic-dependent tests. If aioquic is unavailable, those tests skip gracefully. Install `requirements-dev.txt` for complete QUIC stream validation.

## Important limitations

- The artifact uses native QUIC stream mapping, not custom QUIC extension frames or transport parameters.
- The key schedule is exporter-style and context separated, but does not use live private QUIC TLS exporter bytes.
- Public object-aligned workloads are derived from real public release bytes, but are transfer-model evidence, not captured production registry traces.
- Fairness evidence is conservative: stream payload accounting, local UDP/IPv4 estimates, and emulation rather than a full `tc/netem` or Mininet congestion-control study.
