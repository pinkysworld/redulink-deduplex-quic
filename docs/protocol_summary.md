# ReduLink / Deduplex-QUIC protocol summary

## Scope

ReduLink is a transport-adjacent payload-representation mechanism for cooperative encrypted endpoints. It does not modify the physical link rate and does not require transparent middlebox access to encrypted payloads.

## Main invariant

A reconstructed payload segment is deliverable only if all of the following hold:

1. The frame epoch matches the active dictionary epoch.
2. The referenced chunk identifier is present in the receiver dictionary.
3. The reference is authenticated under the connection context.
4. The reconstructed byte sequence is delivered at the intended stream offset.
5. The reconstruction respects bounded expansion limits.

## Frame sketch

```text
REDULINK_FULL
  epoch_id
  stream_id
  stream_offset
  chunk_length
  chunk_id
  payload
  auth_tag

REDULINK_REF
  epoch_id
  stream_id
  stream_offset
  original_length
  chunk_id
  reference_nonce
  auth_tag

REDULINK_MISS
  epoch_id
  stream_id
  stream_offset
  chunk_id

REDULINK_DICT_ACK
  epoch_id
  chunk_id
```

## Sender behavior

1. Split outgoing payload into fixed or content-defined chunks.
2. Compute `chunk_id = H(epoch || stream_context || chunk)`.
3. If the receiver is known or assumed to have the chunk, send a REF frame.
4. Otherwise send a FULL frame and admit the chunk into the local dictionary.
5. If a MISS arrives, retransmit the corresponding chunk as FULL.

## Receiver behavior

1. Validate FULL frame integrity and admit the chunk into the receiver dictionary.
2. Validate REF frame epoch, authentication, expansion bounds, and dictionary presence.
3. If valid, reconstruct the payload bytes.
4. If not resolvable, emit MISS and do not deliver guessed bytes.

## QUIC integration position

ReduLink should be interpreted as a negotiated representation layer carried by cooperative endpoints. It is not a replacement for QUIC packet numbers, ACKs, congestion control, TLS handshake behavior, or stream semantics. Congestion accounting should be performed over transmitted wire bytes, while application delivery is performed over reconstructed bytes.

## Security defaults

- Per-connection dictionaries by default.
- Short-lived epochs.
- No global cross-user dictionary by default.
- LRU dictionary eviction.
- Per-origin or per-tenant dictionary quotas.
- Bounded expansion ratio.
- Mandatory fallback on reference miss.
- Adaptive disablement when hit rate is too low or CPU cost is too high.

## Evaluation interpretation

The v0.5 artifact is a proof-of-concept simulator and encoder/decoder prototype. It demonstrates byte-exact reconstruction and models effective throughput under conservative frame overhead assumptions. It is not production trace validation and should be extended with larger public corpora such as OCI images, git packs, package repositories, VM snapshots, logs, and backup streams.
