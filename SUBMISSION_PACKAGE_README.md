# ReduLink submission package

This is the clean reviewer-facing package for the journal-oriented ReduLink draft.

## Manuscript

- PDF: `paper/submission/ReduLink_journal_ready_v2_3.pdf`
- DOCX: `paper/submission/ReduLink_journal_ready_v2_3.docx`
- Build script: `scripts/build_manuscript_v2_3.py`

## Validation commands

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests
python3 scripts/check_manuscript_citations.py
python3 benchmarks/generate_target_corpora.py
python3 benchmarks/check_generated_artifacts.py
python3 benchmarks/run_component_performance.py
python3 benchmarks/fetch_external_public_corpora.py
python3 benchmarks/run_real_workload_manifest.py --manifest benchmarks/external_public_manifest.csv --output results/external_public_suite.csv
python3 benchmarks/run_aioquic_scaling_experiment.py
python3 benchmarks/run_quic_bottleneck_emulation.py
```

## Journal-oriented evidence layers

1. Workload byte-saving experiments on deterministic fixtures and reviewer-supplied manifests.
2. Native aioquic QUIC stream mapping with compact binary ReduLink frames.
3. Independently curated public source-release snapshots from Click, Redis, and nginx.
4. Deterministic UDP datagram loss through the aioquic path.
5. Scaling runs at 96 KiB, 512 KiB, and 1 MiB update sizes.
6. Component-cost measurements for chunking, authentication, and binary encoding.
7. Portable bottleneck-emulation analysis over measured QUIC stream-payload bytes.

The package remains carefully scoped: it demonstrates a native QUIC stream mapping, not a custom QUIC extension-frame implementation or a live tc/netem multi-flow congestion study.
