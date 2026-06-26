# ReduLink Threat Model

This document separates security requirements from the current Python model. The
current Python code is a payload-representation and accounting model. It
verifies byte-exact reconstruction and selected fail-closed conditions, but the core model itself is not a production QUIC implementation. The current package includes a native aioquic stream-mapping prototype, but production key-schedule integration, custom extension-frame parsing, replay-window policy, and production privacy enforcement remain future work.

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
| Context binding | REF cannot be replayed across connection, epoch, stream, offset, origin, or dictionary scope. | QUIC exporter-derived keys, epoch id, stream id, offset, dictionary id, nonce, replay window. | HMAC binding and nonce rejection are implemented in the artifact; exporter-derived keys and production replay windows remain pending. |
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
| 0-RTT replay | Early REF is replayed against stale or unauthenticated dictionary state. | References are allowed in QUIC 0-RTT without a bound manifest and fresh epoch salt. | Disable 0-RTT REF by default; require authenticated warm manifest bound to resumption PSK or server identity, dictionary id, chunker parameters, expiration, and fresh epoch salt. | Deployments that enable 0-RTT references accept replay-policy complexity. |
| Migration state confusion | Reference state is incorrectly reused across path, identity, exporter, or policy changes. | Connection migration or policy changes occur while dictionary references remain active. | Continue state only inside the same QUIC connection, exporter context, peer identity, dictionary scope, and epoch; pause REF generation during path validation; reset epoch on exporter, identity, scope, or policy changes. | Path changes can temporarily reduce hit rate or force FULL fallback. |

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

- QUIC TLS exporter-derived ReduLink keys.
- Custom QUIC extension-frame parser integration.
- Production replay-window policy beyond artifact nonce rejection.
- Cross-tenant dictionary isolation enforcement.
- Production MISS frame retransmission timers.
- QUIC final-size, migration, and 0-RTT reference policy.
- Real congestion-fairness experiments against competing flows.

## Related Security Literature To Cite

- Harnik, Pinkas, and Shulman-Peleg, "Side Channels in Cloud Services:
  Deduplication in Cloud Storage."
- Bellare, Keelveedhi, and Ristenpart, "DupLESS: Server-Aided Encryption for
  Deduplicated Storage."
- Modern content-defined chunking side-channel work should be cited where the
  manuscript discusses chosen-content or chunk-boundary leakage.


## Artifact Repair Coverage

The artifact includes `prototypes/redulink_semantic_repair_demo.py`, which models a
dictionary-mismatch case: the sender emits REF, the receiver lacks the referenced
chunk, the receiver would emit MISS, and the sender repairs with FULL. This
checks the fail-closed repair invariant at the representation layer. It does not
prove QUIC loss recovery, replay-window correctness, or cryptographic binding.

## Authenticated artifact additions

The artifact includes `src/redulink_secure.py` and `prototypes/redulink_authenticated_udp_experiment.py`. These components implement artifact-level HMAC binding for epoch, scope, stream id, reconstructed offset, chunk id, length, nonce, and payload hash. The authenticated UDP experiment includes two negative probes: a tampered tag and a replayed nonce. Both are rejected before normal authenticated repair traffic is accepted.

This strengthens the artifact evidence for fail-closed authentication behavior. It does not claim production QUIC security. A production profile should derive keys from the QUIC TLS exporter or equivalent connection-secret material, maintain replay windows appropriate to the transport, and account for key updates, 0-RTT policy, connection migration, and endpoint memory compromise.

## Wire-byte accounting addition

The artifact includes `benchmarks/run_wire_fairness_accounting.py`. The experiment checks the core accounting rule: bottleneck service and congestion accounting use encoded wire bytes, not reconstructed bytes. It is not a competing-flow QUIC congestion-control experiment.


## Native QUIC stream-mapping evidence

The package includes `prototypes/redulink_aioquic_experiment.py`. The experiment uses the aioquic library to run a real QUIC client and server over localhost UDP. ReduLink messages are carried inside a TLS-protected bidirectional QUIC stream. The server intentionally lacks some warm-dictionary entries, reports semantic MISS messages, and reconstructs the update after authenticated FULL repair messages.

Security interpretation: this demonstrates compatibility with native QUIC stream transport and packet protection, but it does not yet bind ReduLink tags to a QUIC TLS exporter and does not implement custom QUIC extension frames. Therefore, it reduces the transport-deployability gap but does not close the production-security gap.

## Key-schedule note

The artifact includes an HKDF-based exporter-style ReduLink key schedule. Tests verify that derived ReduLink secrets change when ALPN, epoch, scope, or connection context changes. This strengthens the artifact's context-binding evidence. It is still not a substitute for a production QUIC TLS exporter hook, because aioquic stream-mapping code in this package does not modify QUIC internals.
