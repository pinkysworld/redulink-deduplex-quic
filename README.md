# ReduLink journal-ready package v3.7

This package contains the ReduLink manuscript and reproducibility artifact for an
applied networking/systems journal submission. The submission snapshot is tagged
`v3.7-journal-submission`; manuscript hashes are pinned in `MANUSCRIPT_SHA256.txt`.

## Main manuscript

- DOCX: `paper/submission/ReduLink_journal_ready_v3_7.docx`
- PDF: `paper/submission/ReduLink_journal_ready_v3_7.pdf`
- Build source: `scripts/build_manuscript_v3_7.py`
  (figures: `scripts/make_journal_figures_v2_8.py`)

Every table and figure in the manuscript is regenerated from the committed
result files, so the reported numbers can be reproduced from this artifact.

## Claim boundary

ReduLink is authenticated, scoped, QUIC-compatible reference substitution for
selected warm-state transfers. It is not a new matching algorithm, not a
universal accelerator, not a replacement for compression or rsync, and not a
custom QUIC extension-frame implementation. The native QUIC artifact maps
compact binary ReduLink records into encrypted aioquic streams. Measured
path-emulation results show that byte savings do not automatically shorten
completion time for small repair-bearing transfers on constrained shared paths;
the measured benefit there is byte-cost reduction at equal congestion fairness.

## Validation commands

Fast reviewer smoke validation (citation check, artifact consistency, selected
unit tests; prints a success summary). It works on a clean clone: steps that
need the hash-pinned external corpora are skipped until you run
`python3 benchmarks/fetch_external_public_corpora.py` once:

```bash
python3 scripts/run_smoke_validation.py
```

Full validation (entire unit suite plus benchmark regeneration):

```bash
python3 scripts/run_full_validation.py
```

The full suite includes aioquic-dependent integration tests. If aioquic is
unavailable, those tests skip gracefully; install `requirements-dev.txt` for
complete QUIC stream validation.

## What is implemented

- Authenticated FULL/REF/MISS reference substitution model with fail-closed
  validation and semantic repair.
- Compact binary ReduLink stream messages over native aioquic QUIC streams.
- Exporter-style HKDF key schedule model for context separation, with a formal
  adversary model and reduction-style analysis in the manuscript (Section 4.5).
- Tamper, replay, wrong-scope, wrong-epoch, wrong-stream, wrong-offset, and
  wrong-length rejection tests.
- Deterministic journal fixtures (with disclosed unchanged fractions), public
  source-release negative pairs, object-aligned public release workloads, a
  Redis-derived layer-like positive case, and an independent hash-pinned PyPI
  package-upgrade trace (`benchmarks/run_pypi_object_trace.py`).
- Real rsync and compression baselines, block-size sensitivity, repeated QUIC
  trials, scaling, component costs, and conservative accounting-layer separation.
- Measured competing-flow fairness and a measured full-duplex userspace path
  emulation (per-direction token buckets + delay shared by both flows), run on
  both byte-stable and real Redis-layered payloads
  (`benchmarks/run_quic_emulated_path.py [--payload demo|redis]`).
- Framing repricing at the measured 108-byte binary wire cost and a zstd
  `--patch-from` dictionary-delta baseline
  (`benchmarks/run_framing_dictionary_baseline.py`).

## Important limitations

- Native QUIC stream mapping, not custom QUIC extension frames or transport
  parameters.
- The key schedule is exporter-style and context separated, but does not use
  live private QUIC TLS exporter bytes.
- Public object-aligned and package-upgrade workloads are derived from real
  public bytes but are transfer-model evidence, not captured production traces.
- Path emulation is userspace (asyncio token bucket + delay), not kernel
  `tc/netem` or Mininet; a privileged-host congestion-control study remains
  future work.
