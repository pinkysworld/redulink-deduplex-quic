# Manuscript evidence map

| Manuscript result | Committed evidence | Regeneration script |
|---|---|---|
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

Every stateful method used by the manuscript reconstructs exact bytes or an
exact ordered object/tree manifest. Diagnostic STATS responses are excluded
from native protocol multipliers and remain separately reported. Historical
timing and path-emulation files are outside the submission evidence set.
