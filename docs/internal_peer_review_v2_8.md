# Internal peer review notes for v2.8

Version 2.8 applies the outcomes of a full pre-submission peer review (see
`docs/peer_review_v2_8.md` for the complete report and verification record).

## Changes from v2.7
- Fixed a section-numbering defect: results subsections 6.1–6.4 are now correctly
  numbered 7.1–7.4 under "7. Workload Results and Baseline Interpretation".
- Corrected reference [11] (FastCDC, IEEE TPDS 2020) from "Y. Hu et al." to the
  correct first author "W. Xia" with the full author list and vol./no.; added
  arXiv IDs to [12]/[13] and repository URLs to [15]/[18].
- Added a system/deployment architecture figure (Figure 1) and a block-size
  sensitivity figure (Figure 4); numbered and captioned all tables (1–13) and
  figures (1–4).
- Added explicit research questions (RQ1–RQ3), a quantitative abstract sentence,
  a Keywords line, a Data and Code Availability statement, and page numbers.

## Verification
- Every manuscript number reconciles to the committed result files (no
  fabricated values).
- Citation checker: 18/18 references cited. Full unit suite: 44/44 passing.

## Remaining honest limits (unchanged, disclosed in §12)
- QUIC stream mapping, not custom QUIC extension frames / transport parameters.
- Exporter-style key-schedule model, not live QUIC TLS exporter bytes.
- Object-aligned / layer-like workloads are transfer-model experiments over real
  public bytes, not captured production traces.
- Conservative wire-byte accounting, not a full tc/netem or Mininet fairness study.

## Submission posture
Suitable for a strong applied networking/systems journal after venue-specific
formatting. For a top-tier systems venue, custom QUIC integration and/or live
packet-level fairness evidence would still be expected.
