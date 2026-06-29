# Evidence hierarchy for v2.8

| Evidence level | What it supports | What it does not prove |
|---|---|---|
| Offline model | FULL/REF reconstruction and byte accounting | Transport behavior |
| Secure model | HMAC binding, tamper rejection, replay rejection | Live QUIC exporter integration |
| UDP repair prototype | Semantic MISS/FULL repair over datagrams | QUIC stream semantics |
| Native aioquic stream mapping | Encrypted QUIC stream transport with compact binary ReduLink records | Custom QUIC extension frames |
| External source-release pairs | Negative evidence for ordinary source tree transfer | Registry/layer transfer gains |
| Object-aligned public release workloads | Positive external transfer-model evidence from real public bytes | Captured production registry traces |
| Repeated QUIC trials | Run-to-run stability for fixed bytes | Internet-scale performance |
| Bottleneck/accounting analysis | Encoded-byte accounting principle | Full congestion-control fairness |
