# ReduLink Threat Model

This document separates security requirements from the current Python model. The
current Python code is a payload-representation and accounting model. It
verifies byte-exact reconstruction and selected fail-closed conditions, but it
is not a production QUIC implementation and does not implement cryptographic key
schedule integration, replay windows, packetization, or production privacy
policy.

## Assumptions

- Endpoints are authenticated by the underlying secure transport.
- ReduLink runs only after negotiation by cooperating endpoints.
- Dictionaries are per-connection by default.
- Shared origin dictionaries are allowed only for public artifacts, one
  administrative trust domain, or explicit tenant/user policy.
- Transparent middlebox operation over QUIC/TLS plaintext is out of scope.

## Security Properties

| Property | Claim | Required mechanism | Current artifact status |
|---|---|---|---|
| Integrity | Receiver output equals sender input or fails closed. | FULL/REF authentication, chunk-id validation, offset binding, length binding. | Modeled by reconstruction and mismatch tests; production crypto is not implemented. |
| Context binding | REF cannot be replayed across connection, epoch, stream, offset, origin, or dictionary scope. | QUIC exporter-derived keys, epoch id, stream id, offset, dictionary id, nonce, replay window. | Specified in protocol text; not implemented in the Python model. |
| Dictionary safety | Receiver admits only authenticated FULL chunks or signed warm-manifest chunks. | Authenticated FULL, manifest commitment, admission policy, eviction policy. | FULL chunk-id checks are modeled; manifest policy is not implemented. |
| Expansion bound | A small REF cannot trigger unbounded receiver work or delivery. | Per-frame, per-stream, and per-epoch reconstructed-byte caps. | Basic accounting and length checks are modeled; full QUIC flow-control enforcement is not. |
| Privacy scope | REF success must not reveal private cross-user content possession in public mode. | Per-connection default, no global cross-user dictionary, explicit per-origin/tenant policy. | Policy is specified; cross-tenant enforcement is not implemented. |

## Privacy Modes

| Mode | Allowed dictionary scope | Leakage risk | Default? | Required controls |
|---|---|---|---|---|
| Public Internet | Per-connection only | Same-connection access-pattern leakage. | Yes | No cross-user references, 1-RTT only, bounded epochs. |
| Public artifacts | Per-origin signed manifest | Artifact-version or popularity inference. | Optional | Public-only content, manifest commitment, expiration. |
| Enterprise VPN | Tenant or administrative domain | Intra-tenant content-existence leakage. | Optional | Tenant policy, quotas, audit, opt-out. |
| CDN/update channel | Origin-scoped public versions | Version-possession inference. | Optional | Public artifact policy, no private-user chunks. |
| Global cross-user | Any user | Private content-possession leakage. | No | Out of scope. |

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

## Chosen-Content Leakage

Like other deduplication systems, ReduLink can create a content-existence oracle
when an adversary can choose payloads or references and observe transfer size,
latency, REF/MISS behavior, fallback traffic, or DICT_ACK behavior.
Per-connection dictionaries remove the cross-user oracle in public-WAN mode, but
they do not remove all leakage inside one connection, one origin, one tenant, or
one administrative domain. Shared dictionaries are therefore permitted only for
public artifacts, same-tenant deployments, or explicitly accepted policy
domains; private global cross-user dictionaries are a non-goal.

Observable signals include:

- Wire byte count and effective transfer size.
- Timing and application-visible latency.
- MISS count, fallback FULL size, and repair timing.
- DICT_ACK presence, absence, or generation changes.
- Reference disablement or epoch reset behavior.

Mitigations are policy-specific: default per-connection dictionaries, short
epochs, no 0-RTT references by default, public-only manifests for public
artifact mode, per-tenant quotas, and constant-error or padding policies where a
deployment accepts the overhead.

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

## Related Security Literature To Cite

- Harnik, Pinkas, and Shulman-Peleg, "Side Channels in Cloud Services:
  Deduplication in Cloud Storage."
- Bellare, Keelveedhi, and Ristenpart, "DupLESS: Server-Aided Encryption for
  Deduplicated Storage."
- Modern content-defined chunking side-channel work should be cited where the
  manuscript discusses chosen-content or chunk-boundary leakage.
