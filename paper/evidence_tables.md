# Manuscript evidence map

| Manuscript result | Committed evidence | Regeneration script |
|---|---|---|
| Production exact-blob residency | `results/ibm_registry_trace_residency_v3_17.csv` and `.json` | `benchmarks/run_ibm_registry_trace_residency_v3_17.py` |
| Pinned compressed registry layers and chunk sensitivity | `results/public_registry_layer_study_v3_17.*` and `results/public_registry_layer_chunk_sensitivity_v3_17.*` | `benchmarks/run_public_registry_layer_sensitivity_v3_17.py` |
| Linux kernel-path completion, TTFB, CPU, packets, and bytes | `results/linux_netem_quic_path_v3_17.csv`, `.json`, and `_summary.csv` | `benchmarks/run_linux_netem_quic_path.py` |
| Same-connection QUIC multistream isolation | `results/quic_multistream_experiment_v3_17.csv` and `.json` | `benchmarks/run_quic_multistream_experiment.py` |
| Synchronized competing-flow fairness | `results/quic_competing_fairness_v3_17.csv` and `.json` | `benchmarks/run_quic_competing_fairness_v3_17.py` |
| CPU, completion, stream-byte, and TTFB scaling | `results/cpu_throughput_scaling_v3_17.csv`, `.json`, and `_summary.csv` | `benchmarks/run_cpu_throughput_scaling_v3_17.py` |
| Public named-object methods | `results/external_object_workload_suite.csv` | `benchmarks/run_external_object_workload_suite.py` |
| Raw public trees, including decoded-wire exactness | `results/external_public_suite.csv` | `benchmarks/run_real_workload_manifest.py` |
| Real rsync | `results/rsync_baseline_external_public.csv` | `benchmarks/run_rsync_baseline_manifest.py` |
| zstd prior-stream dictionary at window_log 21 and 24 | `results/framing_dictionary_baseline.csv` and `.json` | `benchmarks/run_framing_dictionary_baseline.py` |
| PyPI object pairs | `results/pypi_version_pair_object_study.csv` and `.json` | `benchmarks/run_pypi_version_pair_object_study.py` |
| Object chunk-size sensitivity | `results/object_chunk_size_sensitivity.csv` and `.json` | `benchmarks/run_object_chunk_size_sensitivity.py` |
| Native raw and ReduLink flow rows | `results/quic_flow_comparison.csv` and `.json` | `benchmarks/run_quic_flow_comparison.py` |
| Same-layer protocol accounting | `results/protocol_stream_byte_accounting.csv` and `.json` | `benchmarks/run_protocol_stream_accounting.py` |
| Native workload controls | `results/aioquic_workload_cases.csv` and `.json` | `benchmarks/run_aioquic_workload_cases.py` |
| Dictionary-capacity sweep | `results/aioquic_scaling_experiment.csv` and `.json` | `benchmarks/run_aioquic_scaling_experiment.py` |
| Semantic-miss sweep | `results/quic_miss_rate_sensitivity.csv` and `.json` | `benchmarks/run_quic_miss_rate_sensitivity.py` |
| Derived deployment envelope | `results/deployment_envelope.csv` and `.json` | `benchmarks/derive_deployment_envelope.py` |

Every stateful method used by the manuscript reconstructs exact bytes or an
exact ordered object/tree manifest. Diagnostic STATS responses are excluded
from native protocol multipliers and remain separately reported. The 13-byte
FIRST_BYTE acknowledgement is likewise reported and excluded from protocol
bytes. Historical asymmetric-clock timing and userspace path-emulation files
are outside the submission evidence set.
