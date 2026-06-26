# ReduLink journal-ready artifact package

This package accompanies the manuscript **ReduLink: Authenticated Reference Substitution for Redundancy-Suppressed Transfers over Encrypted QUIC Streams** by Michél Nguyen, University of the People, ORCID 0000-0001-6834-4422.

The artifact implements a scoped, endpoint-controlled ReduLink representation layer and evaluates it through offline reconstruction, authenticated frame validation, native aioquic QUIC stream mapping, deterministic loss, scaling, component-cost measurements, external public source-release snapshots, and portable bottleneck-emulation analysis. The implementation is intentionally scoped as a **native QUIC stream mapping**, not as custom QUIC extension-frame parsing.

## Key files

- Manuscript DOCX: `paper/submission/ReduLink_journal_ready_v2_4.docx`
- Manuscript PDF: `paper/submission/ReduLink_journal_ready_v2_4.pdf`
- Core model: `src/redulink_model.py`
- Authenticated model: `src/redulink_secure.py`
- Binary stream format: `src/redulink_wire.py`
- Exporter-style artifact key schedule: `src/redulink_key_schedule.py`
- Native aioquic prototype: `prototypes/redulink_aioquic_experiment.py`
- Real-workload manifest runner: `benchmarks/run_real_workload_manifest.py`
- External public corpus fetcher: `benchmarks/fetch_external_public_corpora.py`
- Real rsync baseline runner: `benchmarks/run_rsync_baseline_manifest.py`
- Scaling experiment: `benchmarks/run_aioquic_scaling_experiment.py`
- Bottleneck emulation: `benchmarks/run_quic_bottleneck_emulation.py`
- Internal peer review notes: `docs/internal_peer_review_v2_2.md`
- Evidence hierarchy: `docs/evidence_hierarchy_v2_4.md`

## Quick validation

Install dependencies first:

```bash
python3 -m pip install -r requirements-dev.txt
```

Then run:

```bash
python3 -m unittest discover -s tests
python3 scripts/check_manuscript_citations.py
python3 benchmarks/generate_target_corpora.py
python3 benchmarks/check_generated_artifacts.py
python3 benchmarks/run_component_performance.py
python3 benchmarks/fetch_external_public_corpora.py
python3 benchmarks/run_real_workload_manifest.py --manifest benchmarks/external_public_manifest.csv --output results/external_public_suite.csv
python3 benchmarks/run_rsync_baseline_manifest.py --manifest benchmarks/external_public_manifest.csv --output results/rsync_baseline_external_public.csv
python3 benchmarks/run_aioquic_scaling_experiment.py
python3 benchmarks/run_quic_bottleneck_emulation.py
```

Most tests that require aioquic skip when aioquic is unavailable, so non-QUIC artifact checks remain reviewable in minimal environments.

## Scope

Implemented: byte-exact FULL/REF reconstruction, authenticated frame validation, replay/tamper rejection, semantic MISS/FULL repair, compact binary stream encoding, native aioquic stream mapping, deterministic loss proxy, local UDP datagram-byte accounting, component-cost reporting, deterministic workload fixtures, pinned public text fixtures, hash-pinned external public source-release snapshots, real rsync baseline runs, reviewer-supplied workload manifest runner, scaling measurements, and bottleneck-emulation analysis over measured QUIC stream payload bytes.

Not implemented: custom QUIC extension frames, QUIC transport-parameter negotiation, direct TLS exporter extraction from aioquic internals, 0-RTT dictionary enforcement inside the transport, migration-policy enforcement, production-scale OCI/VM/Git-pack corpora, and kernel netem/tc multi-flow congestion experiments.
