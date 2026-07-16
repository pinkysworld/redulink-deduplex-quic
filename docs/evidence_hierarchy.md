# Evidence hierarchy for v3.17

| Evidence | Controlled property | Supported inference | Excluded inference |
|---|---|---|---|
| IBM registry trace, complete archive | Exact blob URI, observed bytes, timestamp, anonymized client, true byte-bounded LRU | Same-client exact full-blob residency upper bound for the four source-classified production zones | Authorized client cache hit rate, payload alignment, or ReduLink bytes |
| Pinned public registry layers | Immutable index/platform manifest, blob digest and length, whole-layer CAS removed first | Exact fixed-chunk identity within changed compressed layers on three update pairs | Registry-wide prevalence or uncompressed-layer behavior |
| Isolated Linux tc/netem matrix | Reno, rate, RTT, random loss, paired order, one client clock, qdisc deltas | Completion, TTFB, endpoint CPU, and encrypted kernel-queue cost in 16 controlled conditions | Multi-host Internet behavior or other congestion controllers |
| Same-connection multistream study | One live exporter, actual stream IDs, one miss-heavy blocker and four warm-hit objects | Completion isolation from independent QUIC streams in the measured condition | Custom QUIC frames, free capacity, 0-RTT, or migration |
| Synchronized competing-flow study | Post-setup application barrier and calibrated encoded work | Jain fairness of encoded application goodput for three Reno cases | Fairness of reconstructed value or general Internet fairness |
| Paired CPU/TTFB scaling | Fresh verified localhost connection, 64 KiB to 32 MiB, combined process CPU | Python implementation scaling and whole-object pre-encoding cost | Optimized native throughput |
| Secure model and malformed-input tests | Context, replay, length, quota, dictionary, and repair checks | Enumerated fail-closed implementation behavior | Formal verification or endpoint-compromise security |
| Hash-pinned public releases and wheels | Exact archive/wheel bytes and ordered object extraction | Method bytes on the named pairs | Production traffic weighting |
| Real rsync baseline | Recursive update plus canonical tree-manifest equality | Exact file-tree transfer bytes on three public pairs | General rsync performance |
| Verified zstd raw-content dictionary | Pinned level/window, exact decompression and SHA-256 | Prior-stream dictionary bytes on the named pairs | RFC 9842 interoperability |
| Capacity and semantic-miss sweeps | One controlled state variable and exact reconstruction | Profile-specific residency failure and `B(m)=15914+1149m` | Population statistics or latency |
| Independent compressed control | No warm semantic reuse | Expansion under record overhead | All compressed formats |

All current timing claims come from the v3.17 symmetric-clock experiments.
Earlier timing, userspace shaping, and failed macOS dummynet attempts are not
submission evidence.
