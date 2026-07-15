# Implemented ReduLink protocol profile

This document describes the executable profile in
`prototypes/redulink_aioquic_experiment.py` and `src/redulink_wire.py`. ReduLink
is an application codec carried in a QUIC bidirectional stream. It does not add
QUIC frame types or transport parameters.

## Assumptions

- Sender and receiver are cooperating endpoints of one server-authenticated
  QUIC connection. Application-level client authorization is assumed and is not
  implemented by the artifact.
- Receiver state is provisioned out of band or agreed by a trusted manifest.
- The prototype authenticates the server certificate only.
- aioquic 1.3.0 does not expose a TLS exporter through its public API, so the
  artifact uses a fresh private exporter surrogate per run. A production
  integration must call TLS-Exporter with the private-use label
  `EXPERIMENTAL-ReduLink-v1`, the canonical 32-byte context described below,
  and a 32-byte output. RFC 5705 permits labels beginning with `EXPERIMENTAL`
  without registration. A nonexperimental deployment must register its label.
- Cross-user global dictionaries are outside the supported deployment model.

## Message sequence

| Step | Direction | Message | Purpose |
|---|---|---|---|
| 1 | Client to server | `HELLO` | Version, chunk size, frame count, input length, and SHA-256 digest |
| 2 | Client to server | `FRAME(FULL)` or `FRAME(REF)` | Ordered initial representation records |
| 3 | Client to server | `END_ROUND` | Ends the initial record round |
| 4 | Server to client | `MISSING` | One batched list of unresolved reference metadata |
| 5 | Client to server | repair `FRAME(FULL)` | Authenticated literals for validated missing references |
| 6 | Client to server | `FINISH` | Requests final sequence, length, and digest checks |
| 7 | Server to client | `STATS` | Experiment diagnostics, excluded from protocol evidence |

There is no `DICT_ACK` in the implemented profile. Warm-state advertisement,
admission, revocation, and synchronization are future protocol work.

## Binary records

A FULL or REF record carries:

- sequence number and repair flag;
- record kind;
- epoch and UTF-8 scope;
- a 62-bit application-stream context;
- reconstructed offset and declared chunk length;
- nonce;
- 128-bit keyed chunk identifier;
- 128-bit record tag;
- literal payload for FULL only.

The encoded record costs 85 fixed bytes, including the four-byte message-length
prefix and one-byte message type, plus the scope and any FULL payload. The
native experiment uses a 16-byte scope, so a record costs 101 bytes before a
FULL payload. The object suite uses a 27-byte scope and therefore costs 112
bytes before a FULL payload.

## Context and authentication

Both endpoints derive a connection context as SHA-256 over the versioned,
length-prefixed ALPN and an authenticated application-session identifier. The
TLS-exporter context is SHA-256 over a separate versioned encoding of ALPN,
scope, and that connection context. In the artifact, client and server call the
connection-context derivation separately over one per-run shared identifier.
This checks endpoint-independent agreement but does not substitute for a live
TLS exporter.

The subsequent key schedule canonically length-prefixes the protocol label,
ALPN, scope, connection context, application-stream context, direction, and
epoch before HKDF expansion. Length prefixes prevent the delimiter ambiguity
that existed in an earlier artifact version.

The keyed chunk-identifier transcript is its versioned domain label followed by
an unsigned 64-bit epoch, length-prefixed UTF-8 scope, and 32-byte chunk
SHA-256. The record transcript is its own versioned label followed by a one-byte
kind, unsigned 64-bit epoch, length-prefixed scope, unsigned 64-bit stream
context and offset, 16-byte identifier, unsigned 32-bit length, unsigned 64-bit
nonce, and 32-byte payload SHA-256. Integers are big-endian. HMAC-SHA-256 over
each transcript is truncated to 128 bits. These tags bind representation state
inside the endpoints; QUIC/TLS remains the network-security boundary.

`docs/protocol_test_vectors.json` fixes all transcript bytes, contexts, and
outputs. `tests/test_protocol_vectors.py` reproduces them with independently
written transcript, context, and HKDF code before comparing the production
functions.

## Receiver invariants

The receiver checks authentication and context before mutating accepted state.
It enforces:

- expected sequence number and reconstructed offset;
- expected epoch, scope, stream context, and direction-derived key;
- bounded nonce replay state;
- positive record length no larger than the negotiated chunk size;
- declared total input length no larger than the receiver quota;
- no reconstruction beyond the declared input length or global quota;
- keyed identifier and record-tag validity;
- dictionary content revalidation on every reference;
- exact sequence completion, total length, and SHA-256 digest at `FINISH`.

A missing REF is queued for the single batched `MISSING` response. The sender
accepts a repair request only when its sequence, identifier, and length match an
original REF and when it is unique and in range. The receiver then requires the
repair FULL to match the pending sequence, identifier, length, and offset. HELLO
declares the exact frame count, and the implementation rejects a count that
could not fit in one MISSING message under the 16 MiB message cap.

## Dictionary policy

The implemented dictionary is bounded by chunk count. FULL admission and every
successful REF hit refresh true-LRU recency. Capacity overflow evicts the least
recently used entry. The artifact includes a regression test for hit refresh and
a 16 MiB capacity experiment that exposes sequential LRU thrashing.

## Evidence boundary

Protocol-stream accounting includes HELLO, initial records, END_ROUND, MISSING,
repair records, and FINISH in both directions. It excludes STATS diagnostics.
QUIC packet headers, ACKs, UDP/IP headers, and link-layer bytes are outside this
metric. The current single-host runs support exact reconstruction, state-machine,
and stream-byte claims. They do not support WAN latency, congestion-fairness,
or production-throughput conclusions.

HELLO, MISSING, END_ROUND, and FINISH rely on QUIC/TLS transport protection and
do not carry the per-record HMAC. Reconstructed bytes are buffered until FINISH;
the prototype does not debit reconstructed output against QUIC flow-control
credit. 0-RTT reference semantics and connection-migration state policy are not
implemented.
