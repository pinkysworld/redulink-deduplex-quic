# Internal peer review notes for v3.0

Version 3.0 applies the valid outcomes of the third-round review
(`docs/peer_review_v2_9_round3.md`). The third round found the v2.9 expansion
sound (no new numeric errors; references accurate, incl. RFC 9842 verified) and
the paper converged.

## Changes from v2.9
- R3-1 (applied): added a positioning/comparison table (Table 20, Section 12)
  contrasting ReduLink with in-network RE, rsync/LBFS, HTTP shared-dictionary /
  Compression Dictionary Transport, and local compression, with a forward pointer
  from Section 3.3.
- R3-2 (applied): relabeled the bottleneck-emulation goodput columns as
  application goodput and noted that both flows deliver identical application
  bytes, so the comparison is like-for-like.
- R3-3 (not applied): abstract length left as-is (acceptable for the venue class).

## Verification
- Citation checker 22/22; all table/figure numbers reconcile to results/*.
- 14 pages / ~6.1k words.

## Remaining gaps (unchanged, require new experiments)
Custom QUIC extension frames; live exporter-derived keys; tc/netem or Mininet
fairness over real paths; captured production traces; a quantitative head-to-head
against Compression Dictionary Transport.
