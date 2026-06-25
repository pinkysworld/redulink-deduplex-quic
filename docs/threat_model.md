# ReduLink Threat Model

This document separates security requirements from the current Python model. The
v0.5 code is a payload-representation and accounting model. It verifies
byte-exact reconstruction and selected fail-closed conditions, but it is not a
production QUIC implementation and does not implement cryptographic key
schedule integration, replay windows, packetization, or production privacy
policy.

## Assumptions

- Endpoints are authenticated by the underlying secure transport.
- ReduLink runs only after negotiation by cooperating endpoints.
- Dictionaries are per-connection by default.
- Shared origin dictionaries are allowed only for public artifacts, one
  administrative trust domain, or explicit tenant/user policy.
- Transparent middlebox operation over QUIC/TLS plaintext is out of scope.

## Attack Matrix

| Attack | Oracle or failure mode | Preconditions | Required mitigation | Residual risk |
|---|---|---|---|---|
| Dictionary poisoning | Useful chunks are evicted by attacker-chosen FULL frames. | Attacker can send traffic into a shared dictionary. | Per-tenant quotas, admission refusal, LRU budget, epoch reset, anti-eviction policy for shared dictionaries. | Mostly denial of service; bounded by memory and quota policy. |
| Chosen-chunk probing | REF success/MISS/timing reveals whether receiver has content. | Sender can choose references and observe fallback behavior. | Per-connection default, no speculative cross-user references, public-artifact-only shared dictionaries, rate limits, constant-error policy where needed. | Per-origin dictionaries may still leak public-artifact popularity. |
| Cross-user leakage | Shared dictionary exposes private-user content existence. | Dictionary is shared across users or tenants. | Exclude global/private cross-user dictionaries; require explicit trust domain or tenant policy. | Misconfiguration risk remains. |
| Replayed REF | Stale reference reconstructs bytes in the wrong epoch or offset. | Old REF is replayed or accepted after epoch change. | Epoch binding, nonce/replay window, stream offset binding in REF authentication, epoch reset on key/context changes. | Needs production implementation beyond the simulator. |
| Expansion abuse | Small REF causes excessive reconstructed bytes. | Receiver accepts unbounded references. | Per-frame expansion cap, flow-control by reconstructed bytes, REF length equality checks, pending-byte limits. | Large legitimate chunks still require memory policy. |
| MISS storm | Divergent dictionary causes repeated repair traffic. | Sender speculates incorrectly or receiver evicts aggressively. | MISS rate limit, sender backoff, disable references above miss threshold, semantic FULL repair. | Throughput can degrade to raw FULL mode. |
| CPU exhaustion | Chunking or validation cost dominates transfer. | Adversary sends pathological inputs or high frame rate. | Adaptive disablement, chunking budget, validation rate limits, fast negative controls. | Implementation-specific tuning required. |

## Current Test Coverage

- Byte-exact FULL/REF reconstruction.
- Random-data negative control.
- Warm-dictionary gain.
- REF miss fail-closed behavior.
- FULL and REF length mismatch fail-closed behavior.
- Miss-rate fallback/accounting model coverage.

## Not Yet Implemented In The Python Model

- Cryptographic authentication tags and QUIC exporter integration.
- Replay windows and reference nonce cache.
- Cross-tenant dictionary isolation enforcement.
- Production MISS frame retransmission timers.
- QUIC packet loss, ACK, final-size, migration, and 0-RTT behavior.
- Real congestion-fairness experiments against competing flows.
