# Prototypes

The prototype directory contains endpoint-level checks that make the artifact more concrete than an offline byte-accounting model. Version 2.2 includes a native aioquic stream-mapping experiment. It exercises real QUIC handshake and bidirectional streams, while deliberately avoiding custom QUIC extension-frame parser changes.

## TCP endpoint reconstruction demo

`redulink_socket_prototype.py` sends modeled `FULL` and `REF` frames over a
localhost TCP socket. The server reconstructs the update byte-exactly from the
wire frames and a warm dictionary.

```bash
python3 prototypes/redulink_socket_prototype.py demo
```

Manual two-terminal run:

```bash
python3 prototypes/redulink_socket_prototype.py server \
  --warm /path/to/warm.bin \
  --output /tmp/redulink.out \
  --port 9876
```

```bash
python3 prototypes/redulink_socket_prototype.py client \
  --warm /path/to/warm.bin \
  --input /path/to/update.bin \
  --port 9876
```

## Semantic repair demo

`redulink_semantic_repair_demo.py` models the case where the sender believes a
chunk is in the receiver dictionary, sends `REF`, and the receiver lacks that
entry because of mismatch or eviction. The receiver emits a semantic MISS and
the sender repairs with FULL for the same reconstructed position.

```bash
python3 prototypes/redulink_semantic_repair_demo.py --output results/semantic_repair_demo.json
```

The demo reports initial wire bytes, repair wire bytes, MISS count, repair FULL
count, and final reconstruction status. It validates the repair invariant at the
representation layer. It does not exercise QUIC packet numbers, ACK generation,
loss detection, congestion control, 0-RTT, migration, or cryptographic replay
windows.

## UDP semantic repair experiment

`redulink_udp_repair_experiment.py` runs a real localhost UDP endpoint
experiment. The client sends modeled FULL/REF datagrams, the receiver starts
with an intentionally incomplete warm dictionary, missing references trigger
MISS replies, and the client repairs them with FULL datagrams for the same
reconstructed position. A deterministic drop rule forces timeout-based
retransmission, so the run exercises both semantic repair and datagram retry
behavior over real sockets.

```bash
python3 prototypes/redulink_udp_repair_experiment.py --output results/udp_repair_experiment.json
```

This is still not a QUIC implementation. It is a user-space endpoint prototype
that demonstrates the interaction between REF, MISS, repair FULL, timeout, and
byte-exact reconstruction on UDP.

## Authenticated UDP repair experiment

`redulink_authenticated_udp_experiment.py` extends the UDP repair experiment with artifact-level HMAC validation. Each frame is bound to epoch, scope, stream id, reconstructed offset, chunk id, length, nonce, and payload hash. The receiver rejects a tampered tag and a replayed nonce before accepting normal traffic, then repairs dictionary misses with authenticated FULL frames.

```bash
python3 prototypes/redulink_authenticated_udp_experiment.py --output results/authenticated_udp_experiment.json
```

This validates fail-closed authentication behavior in the artifact. It does not replace native QUIC packet protection or TLS exporter-derived keys.


## Native aioquic stream-mapping experiment

`redulink_aioquic_experiment.py` runs a real localhost QUIC client and server with the `aioquic` library. The client opens a QUIC bidirectional stream, sends authenticated ReduLink FULL/REF messages, receives semantic MISS reports from the server, repairs missing references with authenticated FULL messages, and verifies byte-exact reconstruction.

```bash
python3 prototypes/redulink_aioquic_experiment.py --output results/aioquic_native_experiment.json
```

This is a native QUIC stream-mapping prototype, not a custom extension-frame implementation. It exercises QUIC handshake, TLS-protected streams, stream flow control, packetization, ACK/loss machinery inside aioquic, and encrypted UDP transport. It does not yet modify aioquic internals to add Deduplex-QUIC extension frames or transport parameters.
