# ReduLink / Deduplex-QUIC protocol summary

## Scope

ReduLink is a transport-adjacent payload-representation mechanism for cooperative encrypted endpoints. It preserves the physical link rate and operates without transparent middlebox access to encrypted payloads.

## Delivery invariant

A reconstructed payload segment is deliverable only when:

1. the frame epoch matches the active dictionary epoch;
2. the referenced chunk is present in the receiver dictionary;
3. the reference authenticates under the connection context;
4. the reconstructed bytes map to the intended stream offset; and
5. the reconstruction remains within the configured expansion bound.

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
3. Send REF when the receiver is known or expected to hold the chunk.
4. Otherwise send FULL and admit the chunk to the local dictionary.
5. Retransmit FULL after MISS.

## Receiver behavior

1. Validate FULL integrity and admit the chunk to the receiver dictionary.
2. Validate REF epoch, authentication, expansion bound, and dictionary presence.
3. Reconstruct payload bytes only after successful validation.
4. Emit MISS when a reference cannot be resolved.

## QUIC integration

ReduLink is a negotiated representation layer carried by cooperative endpoints. It does not replace QUIC packet numbers, ACKs, congestion control, TLS handshake behavior, or stream semantics. Congestion control is charged by transmitted wire bytes. Application delivery uses reconstructed bytes.

## Security defaults

- Per-connection dictionaries by default.
- Short-lived epochs.
- No global cross-user dictionary by default.
- LRU dictionary eviction.
- Per-origin or per-tenant dictionary quotas.
- Bounded expansion ratio.
- Mandatory FULL fallback on reference miss.
- Adaptive disablement when hit rate is low or processing cost is high.

## Evaluation status

The v0.5 implementation demonstrates byte-exact reconstruction and effective-throughput modeling under conservative frame-overhead assumptions. The current measurements are suitable for method validation. Broader performance claims require larger public corpora, for example OCI images, git packs, package repositories, VM snapshots, structured logs, and backup streams.
