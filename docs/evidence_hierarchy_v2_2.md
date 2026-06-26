# Evidence hierarchy, Version 2.2

| Evidence layer | Implemented artifact | What it supports | What it does not prove |
| --- | --- | --- | --- |
| Offline model | `src/redulink_model.py` | byte accounting and reconstruction | transport behavior |
| Authenticated model | `src/redulink_secure.py` | context binding, replay/tamper rejection | production QUIC key extraction |
| Binary stream format | `src/redulink_wire.py` | compact stream representation | custom QUIC frame parsing |
| Native QUIC stream mapping | `prototypes/redulink_aioquic_experiment.py` | QUIC handshake, encrypted streams, MISS/FULL repair | extension-frame semantics |
| Scaling runs | `benchmarks/run_aioquic_scaling_experiment.py` | behavior from 96 KiB to 1 MiB | data-center scale |
| Bottleneck emulation | `benchmarks/run_quic_bottleneck_emulation.py` | encoded-byte fairness accounting over measured stream payloads | full kernel/network congestion study |
| Real-workload manifest runner | `benchmarks/run_real_workload_manifest.py` | external corpora can be substituted | included fixtures are not production traces |
