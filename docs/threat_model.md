# ReduLink threat model

ReduLink is a representation layer inside cooperating endpoints. QUIC/TLS is
responsible for confidentiality, peer authentication as configured by the
application, integrity on the network path, loss recovery, flow control, and
congestion control. ReduLink's record HMAC binds decoded representation state
inside the endpoints. It is not an independent network-security boundary.

## Assumptions

- An application authorizes both endpoints and selects an appropriate QUIC
  authentication policy. The current native artifact verifies only the server
  certificate.
- Receiver dictionaries are preprovisioned or agreed by a trusted, hash-pinned
  or signed manifest. Dictionary negotiation is not implemented.
- Per-connection or per-origin dictionaries are the conservative default.
  Private global cross-user dictionaries are excluded.
- The artifact derives ReduLink keying material from the live TLS 1.3 exporter
  independently at both endpoints and rejects unequal outputs. The invocation
  uses the private-use label `EXPERIMENTAL-ReduLink-v1`, a canonical 32-byte
  context, and a 32-byte output. Since aioquic 1.3.0 has no public exporter API,
  the artifact uses a strict version-gated private bridge and retains only its
  label-specific secret. A production implementation should use a public API
  and a registered nonexperimental label.
- Endpoint compromise and malicious code running with access to plaintext or
  ReduLink secrets are outside the protection boundary.

## Security properties and status

| Property | Required behavior | Artifact evidence | Residual limitation |
|---|---|---|---|
| Exact output | Accept only the complete declared byte sequence and digest | Length, sequence, offset, and SHA-256 completion checks | Tests are not a formal proof |
| Context binding | Reject records from another epoch, scope, connection, direction, stream context, or offset | Live endpoint TLS exporter agreement, canonical key context, public vectors, and record-tag tests | Private aioquic hook, server-only certificate authentication, and shared application-session fixture |
| Replay control | Reject duplicate or sufficiently old nonces with bounded memory | Heap-backed 4,096-entry `NonceWindow`, duplicate/old tests, and a 100,000-nonce bound regression | Production policy for long-lived connections is unspecified |
| Dictionary integrity | Recompute a keyed identifier over referenced bytes before acceptance | Corrupted-entry and wrong-scope tests | Manifest admission policy is outside the protocol |
| Expansion bound | Enforce per-record, declared-transfer, and global reconstruction limits | HELLO length and quota tests | QUIC delivery credit is not coupled to reconstructed bytes |
| Repair integrity | Match each repair request and literal to one original missing REF | Duplicate, out-of-range, non-REF, identifier, and length tests | Repair is one batch; v3.17 measures the resulting first-byte cost |
| Repair bound | Require the HELLO frame count and one MISSING batch to fit the 16 MiB message cap | Maximum-item encoder, decoder, and HELLO tests | Multi-batch repair is not implemented |

## Principal threats

| Threat | Failure or oracle | Mitigation | Residual risk |
|---|---|---|---|
| Chosen-content probing | REF success or repair size reveals content possession | Per-connection default, authorization, public-only shared manifests, padding or minimum-size policy | Same-context access patterns remain visible |
| Cross-user leakage | Shared dictionary reveals private content existence | Do not use global private-user dictionaries; partition by origin or tenant | Misconfiguration remains possible |
| Dictionary poisoning | Attacker-chosen FULL records evict useful state | Authenticate FULL, bound capacity and quotas, restrict admission | Bounded denial of service remains possible |
| Chosen eviction | Eviction changes later REF/MISSING behavior | Isolated dictionaries, quotas, rate limits, disable references after high miss rates | Shared scopes retain state-dependent leakage |
| Replay or stale context | Old record reconstructs in another transfer | Canonical context, epoch, stream context, offset, nonce window | Key or endpoint compromise defeats the check |
| Expansion abuse | Small reference triggers excessive output or work | Positive chunk bound, declared length, reconstruction quota | Large authorized transfers still consume resources |
| MISS storm | Divergent state causes repair amplification | Batched repair, sender validation, miss threshold and raw-transfer fallback | Performance can approach or exceed raw transfer |
| 0-RTT replay | Early reference uses stale receiver state | Disable 0-RTT references in this profile | A future 0-RTT design requires separate analysis |
| Migration confusion | State is reused after identity or policy changes | Keep state inside one connection and reset epoch when key, identity, scope, or policy changes | Migration integration is not implemented |

## Observable leakage

An authorized peer can observe protocol byte count, REF/MISSING outcomes, repair
size, timing, and whether reference use is disabled. The v3.17 path and scaling
experiments confirm that pre-encoding changes first-byte timing. Authentication
does not remove these deduplication side channels. Deployment policy may require
partitioned dictionaries, short epochs, padding, rate limits, public-only
manifests, or disabling ReduLink for sensitive or low-reuse objects.

## Verification order

`verify_frame` itself checks the HMAC over the record's own fields before
reporting a record-context mismatch. For an authentic record, it then checks
epoch, scope, stream context, offset, length, replay state, and dictionary bytes
before acceptance. The native receiver performs public state-machine checks,
including HELLO presence, phase, sequence range, and reconstruction quotas,
before calling `verify_frame`; those checks have distinct protocol errors. It
buffers reconstructed output until FINISH, then fails closed unless the complete
sequence set, length, and digest match.

## Deliberately unimplemented security work

- Public-API exporter integration, independent-stack interoperability, and
  mutual client authentication.
- On-wire dictionary discovery, admission, revocation, and synchronization.
- Cross-tenant policy enforcement.
- 0-RTT reference semantics and connection-migration state policy.
- Coupling reconstructed-byte release to QUIC flow-control credit and
  incremental delivery before FINISH.
- Formal verification, memory-safety proof, and production denial-of-service
  analysis.

The manuscript cites prior work on deduplication side channels and server-aided
deduplicated encryption. Those references motivate the conservative dictionary
scope; ReduLink does not claim to solve the general content-existence oracle.

For an idealized 128-bit record tag, `q` independent online guesses succeed
with probability at most approximately `q / 2^128`. This is distinct from the
birthday collision probability for `n` idealized 128-bit keyed identifiers,
approximately `n(n-1) / 2^129`. The final declared-output SHA-256 rejects an
incorrect complete reconstruction unless that digest check also fails. These
are qualified idealized bounds, not a protocol-composition proof.
