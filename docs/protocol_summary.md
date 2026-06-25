# ReduLink / Deduplex-QUIC Protocol Appendix

This appendix summarizes ReduLink as an implementable representation layer for
cooperative encrypted endpoints. It is intentionally narrower than a complete
transport specification: QUIC packetization, packet numbers, ACK processing,
TLS, and congestion-control algorithms remain QUIC responsibilities.

The v0.5 model uses one consistent logical frame vocabulary: `FULL`, `REF`,
`MISS`, and `DICT_ACK`. Earlier manuscript sketches used `DEDU_*` names; those
are now treated as presentation aliases only and should not be mixed into the
normative text.

## A.1 Terminology

- **Chunk**: a contiguous byte string produced by fixed-size or
  content-defined chunking.
- **Chunk identifier**: an authenticated digest over the active epoch,
  stream context, and chunk bytes.
- **Dictionary**: bounded endpoint state mapping chunk identifiers to chunk
  bytes.
- **Epoch**: a dictionary lifetime and keying scope. References are valid only
  inside the active epoch.
- **FULL frame**: a frame carrying chunk bytes.
- **REF frame**: a frame carrying an authenticated reference to a chunk already
  present at the receiver.
- **MISS frame**: a receiver request for FULL fallback after a reference cannot
  be resolved.
- **DICT_ACK frame**: an optional acknowledgement that a receiver admitted a
  chunk to its dictionary.
- **Wire bytes**: bytes transmitted on the congestion-controlled path.
- **Reconstructed bytes**: application payload bytes delivered after successful
  validation and dictionary lookup.

## A.2 Deduplex-QUIC Integration Profile

ReduLink can be carried either as an application mapping inside QUIC STREAM data
or as negotiated QUIC extension frames. The paper's Deduplex-QUIC profile models
the second form because it makes stream offset, flow-control, and loss-repair
semantics explicit.

Negotiation uses a transport-parameter-style capability block:

```text
redulink_parameters {
  version
  chunker = fixed | cdc
  target_chunk_size
  max_dictionary_chunks
  max_reference_expansion
  max_pending_reconstructed_bytes
  max_miss_rate
  dictionary_scope = connection | origin
  speculative_references = true | false
  zero_rtt_references = false
}
```

The conservative default is 1-RTT only: references are disabled in 0-RTT unless
the application authenticates a warm dictionary manifest and accepts replay
risk. Unknown ReduLink frame types follow QUIC extension-frame behavior: peers
that have not negotiated ReduLink must treat them as protocol errors or carry
ReduLink only inside application data. ReduLink frames are ack-eliciting when
they carry stream-reconstruction consequences. Congestion control accounts for
transmitted frame bytes; stream and connection flow control account for
reconstructed bytes.

## A.3 Frame Types

```text
REDULINK_FULL {
  epoch_id
  stream_id
  stream_offset
  chunk_length
  chunk_id
  payload
  auth_tag
}

REDULINK_REF {
  epoch_id
  stream_id
  stream_offset
  original_length
  chunk_id
  reference_nonce
  auth_tag
}

REDULINK_MISS {
  epoch_id
  stream_id
  stream_offset
  chunk_id
}

REDULINK_DICT_ACK {
  epoch_id
  chunk_id
  dictionary_generation
}
```

`REDULINK_FULL` admits new bytes to the receiver dictionary after integrity and
context validation. `REDULINK_REF` reconstructs bytes only when the referenced
chunk is present and authenticated for the active context. `REDULINK_MISS`
forces conservative FULL fallback. `REDULINK_DICT_ACK` allows senders to avoid
speculative references when conservative synchronization is required.

The v0.5 simulator uses conservative model overheads of 24 bytes for `FULL`
metadata and 32 bytes for `REF` metadata. These constants are accounting inputs,
not a final QUIC wire encoding. A final encoding must recompute overhead from
varint lengths, connection ID policy, authentication-tag choice, and any
extension-frame type assignments.

## A.4 Sender State Machine

| State | Meaning | Exit condition |
|---|---|---|
| `disabled` | Sender emits only FULL frames. | Negotiation succeeds and policy allows ReduLink. |
| `learning` | Sender emits FULL and records chunks as candidates. | Receiver sends DICT_ACK or speculative mode is enabled. |
| `conservative-acked` | Sender references only chunks acknowledged by DICT_ACK for the active dictionary generation. | Eviction, epoch reset, or high miss rate. |
| `speculative` | Sender may reference expected receiver chunks before DICT_ACK. | MISS rate or policy disables speculation. |
| `repair` | Sender responds to MISS with FULL for the affected offset and chunk. | Repair FULL is acknowledged or stream is reset. |
| `epoch-reset` | Sender stops references, rotates epoch, and relearns dictionary state. | New epoch is acknowledged. |

Per chunk, the sender tracks:

```text
candidate -> dict_acknowledged -> referenced_inflight -> stable
candidate -> evicted_or_expired
referenced_inflight -> missed -> repair
stable -> evicted_or_expired
```

1. Negotiate ReduLink support and parameters: chunker, target chunk size,
   dictionary budget, maximum expansion ratio, epoch policy, and whether
   speculative references are allowed.
2. Split outgoing stream bytes into chunks.
3. Compute `chunk_id = H("redulink chunk id" || epoch_id || dictionary_scope ||
   stream_id || stream_offset_policy || chunk_length || chunk)`. If cross-stream
   deduplication is enabled, `stream_id` is replaced by an authenticated origin
   dictionary identifier.
4. If receiver state is known or expected to contain `chunk_id` under the active
   dictionary generation, emit `REDULINK_REF`.
5. Otherwise emit `REDULINK_FULL` and admit the chunk locally.
6. Track observed hit rate, MISS rate, CPU cost, and expansion risk.
7. Disable references or reset the epoch when hit rate is too low, MISS rate is
   too high, dictionary state is ambiguous, or security policy requires it.
8. On `REDULINK_MISS`, retransmit the affected byte range as `REDULINK_FULL`.

## A.5 Receiver State Machine

1. Reject frames whose epoch does not match the active epoch.
2. For `REDULINK_FULL`, validate the authentication tag and chunk identifier,
   admit the payload to the dictionary, and deliver the bytes at the intended
   stream offset.
3. For `REDULINK_REF`, validate the authentication tag, expansion bound,
   stream offset, original length, nonce, and dictionary presence.
4. Deliver reconstructed bytes only after all REF checks succeed.
5. Emit `REDULINK_MISS` when the referenced chunk is unavailable or policy
   refuses the reference.
6. Apply stream ordering and flow-control rules to reconstructed bytes, while
   applying congestion accounting to transmitted wire bytes.

Additional receiver rules:

- Duplicate FULL or REF for already delivered bytes is idempotent only when the
  reconstructed bytes and final-size state match the prior delivery.
- Conflicting bytes for an already delivered stream offset are a protocol error.
- A REF whose `original_length` does not match the stored chunk length is a
  validation failure.
- A REF for a gap may be buffered only within `max_pending_reconstructed_bytes`;
  otherwise it is rejected or repaired with MISS.
- RESET_STREAM and STOP_SENDING discard pending reconstruction state for that
  stream. A repair FULL must target the same reconstructed offset and cannot
  change QUIC final-size semantics.
- Connection migration does not transfer dictionary state unless the QUIC
  connection context and epoch remain valid.

## A.6 Dictionary Admission, DICT_ACK, and Eviction

Dictionaries are scoped by connection or trusted origin by default. Global
cross-user dictionaries are out of scope unless an explicit privacy-preserving
policy is defined. Implementations should use bounded LRU-style eviction,
per-origin or per-tenant quotas, and short-lived epochs. A receiver may refuse
dictionary admission when memory pressure, tenant policy, or validation failure
requires it.

`DICT_ACK` acknowledges that a validated FULL chunk was admitted to the receiver
dictionary for a specific epoch and dictionary generation. It is idempotent and
may be retransmitted. A sender may rely on it only until the receiver advertises
eviction, rotates the epoch, changes dictionary generation, or exceeds an
agreed lifetime. If eviction is not deterministic or advertised, the sender must
use a short epoch lifetime, conservative reference budget, or speculative mode
with MISS fallback.

Warm or origin dictionaries require an authenticated manifest:

```text
dictionary_manifest {
  dictionary_id
  origin_or_tenant_scope
  epoch_salt
  content_commitment
  chunker_parameters
  expiration
  privacy_policy
}
```

If the manifest is absent, stale, or fails authentication, the peer falls back to
connection-local learning and emits FULL frames until safe receiver state is
established.

## A.7 Reference Miss Handling

A REF miss is not a data-corruption event. It is a synchronization failure that
must fail closed:

1. The receiver does not deliver reconstructed bytes.
2. The receiver emits `REDULINK_MISS` with epoch, stream offset, and chunk id.
3. If MISS is lost, the receiver may retransmit MISS while the stream offset is
   blocked, subject to rate limits.
4. The sender retransmits the affected range as semantic repair using
   `REDULINK_FULL`; this is distinct from QUIC packet retransmission.
5. A duplicate MISS is idempotent. A duplicate repair FULL is accepted only when
   it reconstructs the same bytes at the same offset.
6. Repeated MISS events reduce or disable reference generation.

## A.8 Security Requirements

- Authenticate every FULL and REF frame under the connection context.
- Bind chunk identifiers to epoch, dictionary scope, stream context where
  applicable, canonical length encoding, and chunk bytes.
- Use domain separation for chunk identifiers and reference authentication tags.
- Derive inner ReduLink authentication keys from the QUIC exporter or another
  endpoint-authenticated key schedule. If QUIC AEAD already covers the frame,
  the inner tag may be a commitment used for dictionary safety rather than a
  second transport-authentication layer; the implementation must state which.
- Bound expansion so small references cannot cause unbounded reconstructed
  output.
- Reset epochs on key changes, context changes, or dictionary uncertainty.
- Avoid cross-user dictionaries by default to reduce privacy leakage.
- Rate-limit MISS storms and reference validation work.
- Treat malformed frames, invalid tags, and unexpected epoch identifiers as
  hard validation failures.

Recommended numeric invariants for an implementation profile:

```text
max_reference_expansion <= 64x per frame
max_ref_bytes_before_full <= 1 MiB per stream without fresh FULL
max_pending_reconstructed_bytes <= min(peer MAX_STREAM_DATA, local policy)
max_miss_rate <= 5 percent over a moving epoch window
max_dictionary_chunks <= negotiated memory budget
```

## A.9 Congestion and Flow-Control Accounting

ReduLink does not increase the physical link rate. Congestion control is charged
by transmitted wire bytes. Flow control and application delivery are charged by
reconstructed bytes. This distinction is central to the effective-throughput
claim: a 1 Gbit/s path still transmits at 1 Gbit/s, but the receiver may
reconstruct more than 1 Gbit/s of application payload when references replace
previously admitted chunks.

`MAX_DATA` and `MAX_STREAM_DATA` are consumed by reconstructed bytes. A REF that
would exceed stream credit is blocked or rejected even if its wire encoding is
small. Congestion-window consumption and loss recovery use transmitted bytes.

## A.10 Failure Cases

- **Random or encrypted-compressed payloads**: hit rate stays low; the sender
  should disable references.
- **Dictionary divergence**: receiver emits MISS and sender falls back to FULL.
- **Replay or stale epoch**: frame validation fails and bytes are not delivered.
- **Chunk-id collision or forgery attempt**: authentication and chunk validation
  fail.
- **Expansion abuse**: expansion bounds reject the frame or disable references.
- **CPU exhaustion**: implementations throttle chunking, validation, or
  reference generation.
- **Middlebox deployment attempt**: encrypted payloads prevent transparent
  application unless endpoints cooperate.

## A.11 Evaluation Status

The v0.5 implementation demonstrates byte-exact reconstruction and
effective-throughput modeling under conservative frame-overhead assumptions.
The repository now includes automated tests, baseline comparison commands,
selected artifact measurements, public-artifact benchmark hooks, and CSV-driven
plot generation. Broader performance claims still require larger public corpora
such as OCI layers, git packs, package repositories, VM snapshots, structured
logs, and backup streams.
