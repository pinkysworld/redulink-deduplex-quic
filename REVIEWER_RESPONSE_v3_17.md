# Response to external review of ReduLink v3.15

This response records how v3.17 treats each concern. The revision adds new
experiments rather than answering empirical objections with prose. It is a
substantially stronger submission candidate, but it does not claim guaranteed
acceptance or production readiness.

## Revision strategy

The revision makes four structural changes:

1. replace the two-gate framing with a three-gate model: authorized residency,
   representation alignment, and byte economics;
2. analyze the complete public IBM registry trace and immutable public
   compressed-layer updates;
3. add corrected kernel-path completion, TTFB, packet, multistream, fairness,
   and CPU measurements; and
4. report negative results as load-bearing evidence.

No historical asymmetric-clock result is restored. The Redis-derived transport
fixture remains labeled author constructed, and the IBM trace is used only for
the fields it exposes.

## Major concerns

### M1 - composition and underdeveloped generalizable insight

**Disposition: addressed with a sharper, falsifiable systems insight.**

The paper is now organized around three necessary gates:

- authorized exact state must remain resident in the correct scope;
- the transmitted representation must preserve exact reusable boundaries; and
- avoided literals must exceed record, control, and repair bytes.

The first two gates are independently measured rather than assumed. In the IBM
production trace, a 1 GiB per-client exact-blob LRU gives a 23.7% request-hit
upper bound but only 14.8% of bytes. On three pinned container update pairs,
ordinary whole-layer CAS removes 26.65% of update bytes; the remaining changed
compressed layers preserve at most 0.127% exact fixed-chunk bytes and expand
under ReduLink. For Gate 3, the fixed native profile still verifies
`B(m)=15914+1149m`, with strict benefit through 71 of 90 misses but not 72.

The general contribution is the ordering and separation of these gates. A
request revisit is not equivalent to resident bytes; resident bytes are not
equivalent to aligned transmitted bytes; aligned bytes are not automatically
economic. The measured coefficients remain profile specific.

### M2 - no transport-level evaluation

**Disposition: addressed for a controlled single-host kernel path.**

The new Linux workflow runs 16 tc/netem conditions: two positive fixtures,
5/20 Mbit/s, 20/80 ms RTT, 0/0.5% random loss, Reno, and 20 paired
order-alternated rounds. Client completion and FIRST_BYTE use one client
monotonic clock. Root-qdisc deltas cover encrypted handshake, ACK, close, loss,
and timing-control traffic. Every transfer reconstructs exactly.

Completion is 0.58-0.88 of raw QUIC for the constructed control and 0.34-0.85
for the Redis-derived fixture. The negative result is equally important: TTFB
is 0.98-1.12 and 1.08-1.37 respectively, with all eight Redis-derived intervals
above 1. A synchronized 10 Mbit/s, 40 ms, 0.5% loss experiment reports Jain
fairness of 0.967 for raw/raw, 0.931 for ReduLink/ReduLink, and 0.917 for the
calibrated mixed case. Multi-host Internet behavior remains open.

### M3 - nominal QUIC coupling and exporter surrogate

**Disposition: exporter and multiplexing gaps addressed; extension concern is
out of scope by design.**

The native client and server now derive ReduLink keying material independently
from their live TLS 1.3 contexts and abort if the exporter outputs differ. The
implementation follows the RFC 9846 exporter construction and adds public
vectors checked by independent code. Because pinned aioquic 1.3.0 exposes no
public exporter API, a strict version-gated bridge captures the
post-Server-Finished 1-RTT key-schedule state, immediately narrows the exporter
master secret to the ReduLink label, and retains only that label-specific
secret.

This makes the live QUIC/TLS session load-bearing for record keys. The new
multistream experiment then uses one connection and actual stream IDs 0, 4, 8,
12, and 16. Four warm-hit 64 KiB objects run alongside one miss-heavy 2 MiB
blocker. Multiplexing reduces mean small-object completion to 0.076 of
sequential execution and every small stream completes before the blocker. The
blocker slows to 1.164, and the session interval spans 1. This demonstrates
stream isolation without claiming free capacity.

ReduLink remains an application-stream mapping, not a custom frame or transport
parameter. 0-RTT, migration, and independent-stack interoperability remain
untested.

### M4 - no real workload trace

**Disposition: addressed for residency; alignment is addressed with a separate
negative public-byte study.**

The complete public IBM Docker Registry archive is verified by its published
SHA-1 and parsed: 2,791 JSON files, 40,872,024 records, and seven availability
zones. Following the source paper, Dallas, London, Frankfurt, and Sydney are
production; the internal zones remain separate. A true per-client byte-bounded
LRU models exact same-client full-blob residency. Because authorization changes
and local deletion are absent, the paper labels the result an upper bound.

The trace has identifiers and sizes but not payloads, so it cannot support
alignment. A separate study resolves Redis, httpd, and Alpine update tags to
immutable index and linux/amd64 manifest digests, verifies every compressed
blob, removes whole-layer CAS hits, and tests the changed bytes at 1, 4, and
16 KiB. This separation is now part of the paper's three-gate contribution.

### M5 - security analysis is not mechanized

**Disposition: scope corrected; mechanization remains open.**

Live exporter integration removes the largest implementation mismatch. The
security claim is no longer presented as a novelty pillar: record HMACs bind
endpoint representation state; QUIC/TLS is the network-security boundary.
Public vectors and malformed-state tests demonstrate implementation behavior,
not protocol composition. No ProVerif, Tamarin, formal reduction, memory-safety
proof, or production denial-of-service analysis is claimed.

### M6 - Python scale and no performance axis

**Disposition: addressed for the Python prototype, with an explicit
implementation boundary.**

The paired local study covers 64 KiB, 256 KiB, 1 MiB, 4 MiB, 16 MiB, and
32 MiB, with ten order-alternated rounds and one warmup. At 32 MiB, median
completion and combined endpoint process CPU are both 0.903 of raw QUIC while
stream bytes are 0.099. A severe replay-window scaling defect was found and
fixed: the bounded window now uses a heap plus set and remains at 4,096 entries
through a 100,000-nonce regression.

The same study exposes the remaining cost. Median TTFB is 12.8 versus 265.7 ms
at 16 MiB and 16.5 versus 513.3 ms at 32 MiB. An optimized implementation and
incremental production are still needed for a production performance claim.

## Minor concerns

- **Abstract density:** rewritten around the three-gate claim with only a small
  set of headline values.
- **Table density:** reduced to five tables; detailed rows remain in the
  reproducible artifact.
- **Repeated disclaimers:** the closest-work boundary remains in related work;
  later sections focus on results and empirical limits.
- **Figure 1 readability:** the reverse MISSING and repair paths now use
  separate orthogonal lanes with non-overlapping labels.
- **Tentackle prior art:** still treated only as implementation prior art, with
  no comparative performance inference.
- **Venue choice:** v3.17 is presented as a credible systems submission
  candidate, not proof of acceptance.

## Remaining top-venue gates

The load-bearing review gaps now have evidence, but the following would still
materially strengthen a top-venue submission:

1. multi-host and independent-stack replication under more congestion
   controllers and migration;
2. a production trace that contains both access order and replayable object
   bytes, so residency and alignment can be evaluated on the same workload;
3. an incremental, optimized implementation that removes whole-object
   pre-encoding from TTFB; and
4. mechanized protocol analysis if security becomes a primary contribution.

These are stated as limits rather than silently converted into claims.
