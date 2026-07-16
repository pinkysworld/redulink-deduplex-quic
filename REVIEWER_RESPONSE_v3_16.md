# Response to external review of ReduLink v3.15

This response records how the v3.16 revision treats each concern. It does not
claim that every top-venue blocker is closed. The review's central conclusion
is accepted: without corrected path-level measurements and a real workload
trace, the paper is not yet ready for a top systems or networking venue.

## Revision strategy

The revision makes the strongest defensible changes that can be reproduced in
the current artifact:

1. make the deployment insight explicit and executable;
2. replace the TLS-exporter surrogate with a live endpoint derivation;
3. reduce result density and repeated self-limitation; and
4. preserve the missing transport and workload evidence as named open gates.

No historical latency result has been restored, and no synthetic workload is
relabeled as a production trace.

## Major concerns

### M1 - composition and underdeveloped generalizable insight

**Disposition: substantially addressed, not fully closed.**

The paper is now organized around a two-gate deployment condition:

- avoided literal bytes must exceed commitment plus repair/control bytes; and
- the authorized warm working set must remain resident under the endpoint
  admission and eviction policy.

For the fixed 98,304-byte native profile, every measured miss row is verified
against `B(m)=15914+1149m`. Strict byte benefit holds through 71 of 90 misses
and first fails at 72. The paired 16 MiB capacity rows demonstrate that this
miss threshold is not sufficient by itself: an 8,192-chunk budget admits no
initial references and expands the stream, whereas a 24,576-chunk budget
retains 16,378 references and restores reduction.

This is a reusable preflight method, but its coefficients remain profile
specific. The revision does not claim that ReduLink is uniquely necessary or
best for a demonstrated production deployment.

### M2 - no transport-level evaluation

**Disposition: accepted and deferred.**

The artifact still has no valid multi-host or kernel-path measurements of
completion time, time to first byte, competing-flow fairness, WAN behavior, or
CPU/throughput scaling. The v3.16 text states this as a submission gate. The
withdrawn historical timing results remain excluded because their asymmetric
clock boundary cannot support a latency comparison.

Closing this item requires a fresh, symmetric measurement run on a real Linux
kernel path or multi-host testbed under a standard congestion controller. A
prose revision cannot substitute for that experiment.

### M3 - nominal QUIC coupling and exporter surrogate

**Disposition: exporter gap closed; transport-extension concern remains.**

The native client and server now derive ReduLink keying material independently
from their live TLS 1.3 contexts and abort if the exporter outputs differ. The
implementation follows the RFC 9846 exporter construction and adds public
vectors checked by independent code. Because pinned aioquic 1.3.0 exposes no
public exporter API, a strict version-gated bridge captures the
post-Server-Finished 1-RTT key-schedule state, immediately narrows the exporter
master secret to the ReduLink label, and retains only that label-specific
secret.

This makes the live QUIC/TLS session load-bearing for record keys. It does not
turn ReduLink into a custom QUIC frame or transport parameter, exercise 0-RTT,
or establish independent-stack interoperability. The application-stream design
is intentional; the remaining coupling limitation is explicit.

### M4 - no real workload trace

**Disposition: accepted and deferred.**

The public release and wheel pairs remain reproducible transfer models, not
traffic traces. The author-constructed Redis-derived case remains labeled as a
fixture. No available trace was treated as evidence unless it could validate
both warm-state availability and the content alignment needed by the mechanism.

A future revision needs a captured registry, CDN, backup, or object-store trace
with object identity, version transitions, access order, and bytes sufficient
to replay chunk alignment and bounded cache residency.

### M5 - security analysis is not mechanized

**Disposition: partially addressed, otherwise deferred.**

Live exporter integration removes the largest implementation mismatch. The
security claim remains deliberately narrow: record HMACs bind endpoint
representation state; QUIC/TLS is the network-security boundary. Public vectors
and malformed-state tests demonstrate implementation behavior, not protocol
composition. No ProVerif, Tamarin, formal reduction, memory-safety proof, or
production denial-of-service analysis is claimed.

### M6 - Python scale and no performance axis

**Disposition: accepted and deferred.**

The revision adds no throughput or CPU claim. Python and the 16 MiB native
capacity ceiling remain limitations. A performance contribution requires an
optimized implementation and a corrected transport experiment, not an
extrapolation from application-stream byte counts.

## Minor concerns

- **Abstract density:** rewritten around the two-gate claim with only a small
  set of headline values.
- **Table density:** reduced from twelve tables to seven; detailed capacity,
  miss, workload-control, PyPI, and evidence-hierarchy rows remain in the
  reproducible artifact.
- **Repeated disclaimers:** the closest-work boundary remains in related work;
  later sections focus on results and empirical limits.
- **Tentackle prior art:** still treated only as implementation prior art, with
  no comparative performance inference.
- **Venue choice:** v3.16 is presented as a stronger applied-paper revision,
  not as proof that the top-tier evidence threshold has been met.

## Remaining top-venue gates

Before presenting ReduLink as top-tier ready, the project still needs at least:

1. corrected kernel-path or multi-host transport measurements, including time
   to first byte, completion time, and competing-flow fairness;
2. one replayable production workload trace that validates warm-state
   availability, alignment, and bounded residency; and
3. a performance-oriented implementation/evaluation axis.

Independent-stack exporter interoperability and a mechanized security argument
would materially strengthen the work but do not replace the first two gates.
