# Evidence hierarchy for v3.16

| Evidence | Controlled property | Supported inference | Excluded inference |
|---|---|---|---|
| Secure model and malformed-input tests | Context, replay, length, quota, and dictionary checks | Enumerated fail-closed implementation behavior | Formal verification or endpoint-compromise security |
| Hash-pinned public release pairs | Exact archive bytes and ordered object extraction | Method byte counts on the named pairs | Production prevalence or traffic weighting |
| Recorded PyPI wheel pairs | Exact wheel hashes and ordered members | Object reuse on the four recorded pairs | Package-ecosystem population claims |
| Real rsync baseline | Recursive update plus canonical tree-manifest equality | Exact file-tree transfer bytes on three public pairs | General rsync performance |
| Verified zstd raw-content dictionary | Pinned level 3 and window_log 21, window_log 24 sensitivity, exact decompression and SHA-256 equality | Prior-stream dictionary bytes on the named pairs | RFC 9842 interoperability |
| Canonical raw-tree binary profile | Every encoded message is decoded before reconstruction and final digest comparison | Complete no-miss application-stream serialization bytes | Native QUIC packet behavior |
| Native aioquic stream mapping | Actual encrypted stream, binary messages, exact digest | Protocol-stream bytes and receive-state behavior | WAN latency, congestion fairness, or throughput |
| Chunk-size sweep | Three public object pairs and a byte-equivalent 64 MiB dictionary | Sensitivity to fixed chunk size on the named pairs | Universal optimal chunk size |
| Capacity and miss sweeps | Deterministic workload and one changed state parameter | Sensitivity to matched capacity and repair | Population statistics |
| Derived deployment envelope | Exact native stream-byte rows plus capacity rows | For the measured profile, the algebraic miss threshold and the separate warm-state residency gate | Latency, fairness, packet cost, or workload prevalence |
| Independent compressed control | No warm semantic reuse | Expansion under record overhead | All compressed formats or workloads |

Historical timing, userspace path-emulation, and kernel-path outputs are not
part of the v3.16 submission artifact and do not support its conclusions.
