# ReduLink

Authenticated redundancy-suppressed transmission for effective reconstructed throughput over encrypted WANs.

ReduLink is an endpoint-controlled representation-layer model for replacing repeated payload chunks with compact authenticated references under negotiated dictionary state. The repository also describes a candidate Deduplex-QUIC integration profile, but the runnable artifact is not a QUIC implementation.

The mechanism does not change physical link rate. It can improve effective reconstructed payload throughput only when byte-identical chunks survive across receiver warm state, chunk boundaries, and framing overhead. The evaluation deliberately includes positive, weak, and negative cases.

## Repository contents

```text
src/redulink_model.py                              Canonical encoder/decoder artifact model
src/redulink_proto_v0_5.py                         Backward-compatible wrapper
tests/                                             Reconstruction, safety, plotting, and prototype tests
benchmarks/                                        Reproducible benchmark suites and manifests
prototypes/redulink_socket_prototype.py            Minimal TCP endpoint-reconstruction prototype
scripts/summarize_benchmark_evidence.py            Paper evidence-table generator
scripts/plot_results.py                            General figure generation from CSV
scripts/plot_warm_update_summary.py                Paper-facing warm/update summary plot
results/                                           Generated CSV evidence
figures/                                           Generated plots
docs/protocol_summary.md                           Protocol appendix and candidate Deduplex-QUIC profile
docs/threat_model.md                               Threat model and security scope
paper/                                             Manuscript notes and evidence tables
paper/submission/                                  Rendered DOCX/PDF drafts
.github/workflows/tests.yml                        CI test workflow
LICENSE
CITATION.cff
```

## Scope

Implemented:

- fixed and content-defined chunking model,
- FULL/REF byte-exact reconstruction,
- fail-closed REF miss behavior,
- wire-byte accounting with frame overhead,
- random and compressed negative controls,
- public fixture and deterministic target-class benchmark suites,
- localhost TCP endpoint reconstruction prototype.

Not implemented:

- QUIC packetization, extension-frame parsing, ACK/loss recovery, flow control, migration, or 0-RTT behavior,
- cryptographic authentication tags, QUIC exporter binding, replay windows, or production manifests,
- congestion-fairness or line-rate performance experiments,
- cross-tenant privacy enforcement.

## Run the model

Directory or file input:

```bash
python3 src/redulink_model.py artifact --path /path/to/data --chunker cdc --mode warm
```

Random-data negative control:

```bash
python3 src/redulink_model.py random --size-mib 8 --chunker cdc
```

Structured-log workload:

```bash
python3 src/redulink_model.py synthetic --variant logs --chunker fixed
```

The old `src/redulink_proto_v0_5.py` entrypoint remains as a compatibility wrapper.

## Tests

Fast unit/prototype tests pass from a clean checkout. The public-corpus validation test skips with an instruction if optional fetched corpora are absent.

```bash
python3 -m pip install -r requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
```

For full artifact-data validation, fetch the pinned public fixture first:

```bash
python3 benchmarks/fetch_public_corpora.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
```

## Reproducible benchmarks

Synthetic suite:

```bash
bash benchmarks/run_synthetic_suite.sh
```

Pinned public fixture:

```bash
python3 benchmarks/fetch_public_corpora.py
bash benchmarks/run_public_artifacts.sh --manifest benchmarks/public_artifacts_manifest.csv
```

Deterministic target-class generated fixtures:

```bash
bash benchmarks/run_target_class_suite.sh
python3 benchmarks/check_generated_artifacts.py
```

Optional block-size sensitivity runs:

```bash
bash benchmarks/run_block_size_sensitivity.sh
```

Regenerate paper tables and figures:

```bash
python3 scripts/plot_results.py results/synthetic_suite.csv --output-dir figures
python3 scripts/plot_results.py results/public_artifact_suite.csv --output-dir figures/public_artifacts
python3 scripts/plot_results.py results/target_class_suite.csv --output-dir figures/target_class
python3 scripts/summarize_benchmark_evidence.py
python3 scripts/plot_warm_update_summary.py
```

## Evidence interpretation

The strongest current evidence is that ReduLink can suppress transmitted bytes for suitable warm-state workloads, especially aligned/page-like VM or backup data and selected public changed-version artifacts. It is weak or negative for random data, independent compressed data, and generated cases where chunk identity does not survive. Fixed-block reuse often beats ReduLink on aligned update-like data; ReduLink's contribution is not a superior delta algorithm, but a scoped reference-substitution model with explicit transport, dictionary, miss-repair, privacy, and accounting semantics.

Timing columns are local wall-clock runner measurements (`wall_ms`, `throughput_mib_s_local`, `runner_peak_kib`). They are not production performance or line-rate claims.

## Prototype

```bash
python3 prototypes/redulink_socket_prototype.py demo
```

The prototype sends modeled FULL/REF frames over localhost TCP and verifies byte-exact reconstruction. It does not exercise QUIC behavior.

## Manuscript

Current submission title:

**ReduLink: Authenticated Redundancy-Suppressed Transmission for Effective Reconstructed Throughput over Encrypted WANs**

Subtitle/scope:

**A representation-layer model and candidate Deduplex-QUIC profile**

Rendered drafts are under `paper/submission/`. The v0.9 revision synchronizes the manuscript with target-class evidence, corrected artifact tests, fixed socket accounting, and updated protocol/security framing.

## Citation

Use `CITATION.cff`.

## License

The code is released under the MIT License. Manuscript text remains with the author unless separately licensed.
