# Native aioquic prototype

`redulink_aioquic_experiment.py` implements the ReduLink binary
application-stream mapping used by the submission evidence. It creates a
server-authenticated local QUIC connection, reads the actual application stream
identifier, derives per-stream record state from fresh private inputs, performs
batched semantic repair, and requires exact final length and SHA-256.

The prototype derives matching endpoint secrets from the live TLS 1.3 exporter.
Because aioquic 1.3.0 does not expose a public exporter API, the bridge is
strictly version gated to the audited post-Server-Finished 1-RTT stage. It does
not authenticate a client certificate, negotiate warm dictionaries, or add
custom QUIC frames. The v3.17 harnesses measure controlled single-host Linux
completion, FIRST_BYTE, multistream isolation, fairness, and local process CPU;
they do not establish multi-host Internet behavior, independent-stack
interoperability, or optimized production throughput.
