# Revision history

## v3.16

- Replaced the per-run exporter surrogate with matching live TLS 1.3 exporter
  outputs from both endpoints. The bridge is restricted to pinned aioquic 1.3.0,
  captures the post-Server-Finished 1-RTT key-schedule state, retains only the
  label-specific secret, and fails on version drift or endpoint disagreement.
- Added public TLS-exporter vectors and an independent RFC 9846 formula check.
- Derived and mechanically verified the fixed-profile deployment equation
  `B(m)=15914+1149m`; strict byte benefit holds through 71 of 90 misses and
  first fails at 72.
- Separated miss-cost break-even from the warm-working-set residency gate and
  recorded initial REF/FULL counts in the matched-capacity sweep.
- Rewrote the abstract, introduction, discussion, and conclusion around that
  two-gate deployment condition; reduced the manuscript from twelve tables to
  seven by moving detailed evidence rows to the artifact.
- Added an explicit peer-review response and retained transport timing,
  production traces, mechanized proof, and optimized performance as open work.

## v3.15

- Reframed novelty around a bounded QUIC application-stream mapping rather than
  endpoint redundancy elimination itself; added EndRE, DOT, PACK, CoRE, rsync,
  LBFS, REBL, and HTTP Compression Dictionary Transport to the closest-work
  boundary.
- Replaced delimiter-joined key context with a canonical length-prefixed
  encoding that also binds direction.
- Read the actual aioquic stream identifier and enforced QUIC's 62-bit stream
  and offset range.
- Added a QUIC/TLS-protected declared input length checked against configured
  expectations, per-record expansion checks, and a global reconstruction quota.
- Corrected dictionary behavior to true LRU by refreshing successful REF hits.
- Validated every MISSING item at the sender and every repair against pending
  sequence, identifier, length, and offset state at the receiver.
- Split forward protocol, reverse repair/control, and diagnostic STATS bytes.
  Removed packet, fairness, latency, and throughput inferences from the active
  manuscript.
- Replaced an optimistic object byte model with actual binary frame lengths;
  separated a 4 KiB chunk-token baseline from true whole-object content
  addressing.
- Replaced a byte-count-only rsync check with a canonical tree-manifest check.
- Replaced the unverified zstd patch command with a raw-content-dictionary
  compression and decompression round trip using pinned library versions.
- Extended native capacity evidence through 16 MiB and added a byte-only
  semantic-miss sweep and an independent compressed negative control.
- Corrected the capacity sweep to use matched sender and receiver budgets,
  extended the miss sweep through 100 percent, and added a 0.5 to 16 KiB object
  chunk-size sensitivity sweep.
- Added exact token decoding, bounded object-profile LRU state, serialized
  object headers, deterministic gzip provenance, and semantic regeneration of
  evidence, figures, and the normalized manuscript package.
- Replaced JSON MAC input with fixed binary CID and frame transcripts, added
  public protocol vectors with independent transcript and HKDF tests, and
  specified the exact private-use TLS-exporter invocation and endpoint-independent
  connection context.
- Made the raw-tree baseline reconstruct from decoded wire messages, pinned
  zstd window_log 21 with a window_log 24 sensitivity run, and added fixed-PDF
  claim and source-revision checks.
- Added and distinguished Tentackle TRIP-over-QUIC as close industrial prior
  art.
- Rebuilt the manuscript and figures from the corrected result schema.

Earlier tagged versions remain available in Git history. Their timing and
path-emulation outputs are not evidence for the v3.16 manuscript.
