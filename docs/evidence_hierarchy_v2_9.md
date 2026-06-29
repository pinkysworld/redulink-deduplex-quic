# Evidence hierarchy for v2.9

| Evidence level | What it supports | What it does not prove |
|---|---|---|
| Offline model | FULL/REF reconstruction and byte accounting | Transport behavior |
| Secure model | HMAC binding, tamper rejection, replay rejection | Live QUIC exporter integration |
| UDP repair prototype | Semantic MISS/FULL repair over datagrams | QUIC stream semantics |
| Authenticated UDP prototype | Fail-closed under tamper and replay probes | Production replay-window policy |
| Native aioquic stream mapping | Encrypted QUIC stream transport with compact binary records | Custom QUIC extension frames |
| Scaling experiment | Multiplier/miss behavior as payload grows | Internet-scale performance |
| External source-release pairs | Negative evidence for ordinary source-tree transfer | Registry/layer transfer gains |
| Object-aligned public release workloads | Positive external transfer-model evidence | Captured production registry traces |
| Repeated QUIC trials | Run-to-run stability for fixed bytes | Internet-scale performance |
| Wire-byte / competing-flow / bottleneck accounting | Encoded-byte accounting and fair-share intuition | Full congestion-control fairness |
