# Evidence hierarchy (v3.8)

| Evidence level | What it supports | What it does not prove |
|---|---|---|
| Offline model | FULL/REF reconstruction and byte accounting (model framing) | Transport behavior; wire-priced costs |
| Framing repricing + dictionary-delta baseline (Sec. 7.6) | Wire-format-priced multipliers; the byte superiority of whole-stream zstd delta where its assumptions hold | Registry deployments that cannot retain the exact prior stream |
| Secure model + formal analysis (Sec. 4.5) | MAC-first verification, bounded replay window, tamper/replay rejection; reduction to HMAC EUF-CMA | Machine-checked proof; exporter keying on every path |
| UDP / authenticated-UDP prototypes | Semantic MISS/FULL repair; fail-closed under tamper and replay probes; seq-bound offsets | Production replay policy |
| Native aioquic stream mapping | Encrypted QUIC stream transport, loss handling, scaling, dictionary-budget overflow/recovery | Custom QUIC extension frames |
| Journal fixtures (disclosed unchanged fraction) | Illustrative positive/negative workload shapes | Real-world overlap estimates |
| External source-release pairs | Negative evidence for ordinary source-tree transfer | Registry/layer transfer gains |
| Object-aligned public release workloads | Positive external transfer-model evidence | Captured production registry traces |
| PyPI version-pair study (Sec. 7.5) | Positive/negative evidence from author-independent overlap | Client-trace frequency or population weighting |
| Measured competing flows + userspace path emulation | Encoded-byte accounting, completion/queueing behavior on an emulated grid | Kernel tc/netem, Mininet, or Internet paths |
| Native QUIC miss-rate sensitivity | How semantic repairs erode path-emulation byte savings on one constrained point | A full bandwidth/RTT miss-rate grid |
