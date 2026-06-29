# Internal peer review notes for v2.9

Version 2.9 applies the valid outcomes of the second-round review
(`docs/peer_review_v2_8_round2.md`) and substantially expands the paper.

## Round-2 fixes applied
- M1 (related work): added an HTTP delta / shared-dictionary subsection (RFC 3229,
  VCDIFF/RFC 3284, SDCH, RFC 9842 Compression Dictionary Transport, refs [19]-[22])
  and an explicit differentiation of ReduLink (per-reference authentication,
  fail-closed repair, transport-general abstraction).
- M2 (figure order): figures are now numbered in order of appearance
  (1 architecture, 2 object-aligned, 3 block-size, 4 native QUIC).
- M3 (cross-references): every table (1-19) and figure (1-4) is now referenced
  from the body text.
- m1 (test environment): added a reproducibility note distinguishing deterministic,
  machine-independent byte multipliers from hardware-dependent wall-clock timings.

## Expansion (added "flesh", all from existing evidence)
- Deeper protocol/security model: frame-type table, validation order, dictionary/
  epoch/key-schedule subsections, security-properties table, privacy-modes table
  (sourced from docs/protocol_summary.md and docs/threat_model.md).
- New results surfaced from already-collected data: payload scaling (Table 14),
  wire-byte fairness accounting (Table 16), competing-flow Jain index (Table 17),
  fluid bottleneck emulation across rate/RTT (Table 18), and repair/authentication
  prototypes incl. tamper/replay rejection (Table 19).
- Expanded introduction, related work, methodology, discussion, and limitations.

## Verification
- Citation checker: 22/22 references cited.
- Every table/figure number reconciles to the committed result files.
- Manuscript grew from ~3.4k words / 9 pp (v2.8) to ~5.9k words / 13 pp (v2.9).

## Remaining honest limits (unchanged, disclosed in Section 13)
- QUIC stream mapping, not custom extension frames / transport parameters.
- Exporter-style key schedule, not live QUIC TLS exporter bytes.
- Transfer-model and emulated-fairness evidence, not captured production traces or
  a full tc/netem congestion-control study; transport experiments are localhost.
