# Evidence hierarchy (v3.14 candidate)

| Evidence level | What it supports | What it does not prove |
|---|---|---|
| Offline model | FULL/REF reconstruction and byte accounting (model framing) | Transport behavior; wire-priced costs |
| Framing repricing + dictionary-delta baseline (Sec. 7.6) | Wire-format-priced multipliers; the byte superiority of whole-stream zstd delta where its assumptions hold | Registry deployments that cannot retain the exact prior stream |
| Secure model + formal analysis (Sec. 4.5) | MAC-first verification, bounded replay window, tamper/replay rejection; truncated-HMAC bound under PRF/random-function and digest-collision assumptions | Machine-checked proof; live exporter keying |
| UDP / authenticated-UDP prototypes | Semantic MISS/FULL repair; fail-closed under tamper and replay probes; seq-bound offsets | Production replay policy |
| Native aioquic stream mapping | Server-certificate verification, fresh per-run key surrogate, independently tracked sequence/offset state, encrypted QUIC streams, loss handling | Mutual TLS, live TLS exporter bytes, custom QUIC frames |
| Journal fixtures (disclosed unchanged fraction) | Illustrative positive/negative workload shapes | Real-world overlap estimates |
| External source-release pairs | Negative evidence for ordinary source-tree transfer | Registry/layer transfer gains |
| Object-aligned public release workloads | Exact reconstruction of ordered object names, boundaries, empty objects, and contents with shared warm state | Captured production registry traces |
| PyPI version-pair study (Sec. 7.5) | Positive/negative evidence from real package bytes using the same exact object decoder | Client-trace frequency or population weighting |
| Concurrent localhost diagnostic + userspace path emulation | Encoded-byte accounting and completion/queueing behavior on an emulated grid with 20-round local QUIC repeats | Internet fairness or population-level inference |
| Native QUIC miss-rate sensitivity | How semantic repairs erode path-emulation byte savings on one constrained point | A full bandwidth/RTT miss-rate grid |
| macOS pf/dnctl dummynet QUIC path harness | Reviewer-runnable dry-run rules and local UDP probe viability on macOS | Completed aioquic sweep; WAN, Mininet, Linux tc/netem, or production registry traces |
| Legacy Linux tc/netem result + corrected harness | v3.13 concurrent contention diagnostic; v3.14 isolated order-alternated runner with provenance capture | A rerun of the corrected isolated sweep; WAN, Mininet, or production registry traces |
