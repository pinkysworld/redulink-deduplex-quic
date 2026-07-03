# Evidence hierarchy for v3.3

| Evidence level | What it supports | What it does not prove |
|---|---|---|
| Offline model | FULL/REF reconstruction and byte accounting | Transport behavior |
| Secure model + formal analysis (Sec. 4.5) | HMAC binding, tamper/replay rejection; reduction of unforgeability to HMAC EUF-CMA | Machine-checked proof; live QUIC exporter keying |
| UDP / authenticated-UDP prototypes | Semantic MISS/FULL repair; fail-closed under tamper and replay probes | Production replay-window policy |
| Native aioquic stream mapping | Encrypted QUIC stream transport, loss handling, scaling | Custom QUIC extension frames |
| Journal fixtures (disclosed unchanged fraction) | Illustrative positive/negative workload shapes | Real-world overlap estimates |
| External source-release pairs | Negative evidence for ordinary source-tree transfer | Registry/layer transfer gains |
| Object-aligned public release workloads | Positive external transfer-model evidence | Captured production registry traces |
| Independent PyPI upgrade trace (Sec. 7.5) | Positive/negative evidence from author-independent overlap | pip's current single-archive wire format |
| Measured competing flows (12 rounds) + analytic bottleneck model | Encoded-byte accounting and coexistence indication | Kernel tc/netem or Mininet fairness study |
