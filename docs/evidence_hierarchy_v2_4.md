# Evidence hierarchy, Version 2.4

| Evidence layer | Implemented artifact | What it supports | What it does not prove |
| --- | --- | --- | --- |
| Offline model | `src/redulink_model.py` | Byte accounting, FULL/REF reconstruction, miss failure. | Transport behavior. |
| Authenticated model | `src/redulink_secure.py` | Context binding, replay/tamper rejection, fail-closed checks. | Production QUIC TLS exporter extraction. |
| Exporter-style key schedule | `src/redulink_key_schedule.py` | ALPN, epoch, scope, connection, and stream separation. | Direct integration with aioquic internals. |
| Binary stream format | `src/redulink_wire.py` | Compact stream representation for FULL/REF/MISS/repair. | Custom QUIC frame parsing. |
| Native QUIC stream mapping | `prototypes/redulink_aioquic_experiment.py` | QUIC handshake, encrypted streams, stream payload savings, MISS/FULL repair. | Extension-frame semantics or kernel network behavior. |
| Local UDP datagram accounting | `results/quic_flow_comparison.csv` | UDP payload bytes seen through the local proxy and approximate IPv4/UDP byte estimates. | Link-layer capture, real NIC behavior, or tc/netem fairness. |
| Deterministic journal fixtures | `results/journal_workload_suite.csv` | Positive, weak, and negative workload classes under reproducible inputs. | Production trace representativeness. |
| Hash-pinned external source releases | `benchmarks/fetch_external_public_corpora.py`, `results/external_public_suite.csv` | Independently curated public inputs and negative source-release sanity checks. | OCI/VM/Git-pack/log production workload coverage. |
| Real rsync baseline | `benchmarks/run_rsync_baseline_manifest.py`, `results/rsync_baseline_external_public.csv` | Shows rsync strongly outperforms ReduLink on source-release tree deltas. | ReduLink is not a delta-transfer replacement. |
| Scaling runs | `benchmarks/run_aioquic_scaling_experiment.py` | Behavior from 96 KiB to 1 MiB. | Data-center scale or high-BDP paths. |
| Fairness accounting | `benchmarks/run_wire_fairness_accounting.py`, `benchmarks/run_quic_bottleneck_emulation.py` | Encoded-byte accounting and portable fluid bottleneck analysis. | Full kernel/network congestion-control fairness. |
| Real-workload manifest runner | `benchmarks/run_real_workload_manifest.py` | Reviewer-supplied corpora can be substituted. | Included external corpus is complete enough for all claimed domains. |
