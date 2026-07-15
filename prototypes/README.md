# Native aioquic prototype

`redulink_aioquic_experiment.py` implements the ReduLink binary
application-stream mapping used by the submission evidence. It creates a
server-authenticated local QUIC connection, reads the actual application stream
identifier, derives per-stream record state from fresh private inputs, performs
batched semantic repair, and requires exact final length and SHA-256.

The prototype uses a fresh exporter surrogate because aioquic 1.3.0 does not
expose TLS exporter bytes through its public API. It does not authenticate a
client certificate, negotiate warm dictionaries, add custom QUIC frames, or
support latency, congestion-fairness, or production-throughput claims.
