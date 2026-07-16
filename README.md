# ReduLink v3.16 research artifact

ReduLink is a bounded application-stream representation for cooperating QUIC
endpoints with preprovisioned receiver state. It replaces repeated chunks with
context-bound references and provides batched repair when receiver state is
missing. The contribution is the QUIC mapping, receive invariants, exact byte
accounting, and reproducible evaluation. Endpoint redundancy elimination and
content-addressed substitution are established ideas.

## Submission files

- Manuscript: `paper/submission/ReduLink_journal_ready_v3_16.pdf` and `.docx`
- Journal highlights: `paper/submission/HIGHLIGHTS.txt`
- Manuscript builder: `scripts/build_manuscript_v3_16.py`
- Figure builder: `scripts/make_journal_figures_v3_16.py`
- Manuscript hashes: `MANUSCRIPT_SHA256.txt`
- Source revision used for evidence: `SOURCE_COMMIT.txt`
- Artifact checklist: `PUBLIC_REVIEWER_CHECKLIST.md`

## Supported claims

The artifact supports exact reconstruction, authenticated representation-state
binding, bounded receive behavior, and directional QUIC application-stream byte
counts. It includes hash-pinned public release pairs, recorded PyPI wheel pairs,
whole-object content addressing, fixed-chunk tokens, gzip, a verified zstd
raw-content-dictionary round trip, and real rsync with exact tree-manifest
verification. It also includes a 0.5 to 16 KiB chunk-size sweep with a
byte-equivalent dictionary budget.

The record HMAC is a defensive endpoint-state commitment. QUIC/TLS is the
network-security boundary. The implementation is an application codec on a QUIC
stream, not a custom QUIC frame. The native prototype now derives its record
secret from the live TLS 1.3 exporter on both endpoints and checks that the
outputs match. Because aioquic 1.3.0 has no public exporter API, the bridge is
strictly version gated and hooks the audited post-Server-Finished 1-RTT stage.
The exporter formula, label, context derivation, binary MAC transcripts, and
public test vectors are fixed in `docs/protocol_summary.md` and
`docs/protocol_test_vectors.json`.

The package does not claim WAN latency, congestion fairness, production
throughput, mutual endpoint authentication, on-wire dictionary negotiation, or
superiority to rsync, ordinary compression, or HTTP Compression Dictionary
Transport. Historical timing and path-emulation outputs are not packaged as
submission evidence.

## Validation

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
python scripts/run_smoke_validation.py
python scripts/run_full_validation.py
```

The validators verify the committed manuscript and PDF claims, citations,
result schemas, exact reconstruction checks, and test suite. The local full
validator rebuilds figures and the normalized DOCX package in temporary paths. In CI, the benchmark
commands also regenerate deterministic result tables before the evidence checker
compares their load-bearing fields with the committed rows. External public
archives are fetched separately:

```bash
python benchmarks/fetch_external_public_corpora.py
python benchmarks/run_external_object_workload_suite.py
python benchmarks/run_object_chunk_size_sensitivity.py
python benchmarks/run_rsync_baseline_manifest.py \
  --manifest benchmarks/external_public_manifest.csv \
  --output results/rsync_baseline_external_public.csv
```

The native QUIC evidence can be regenerated with:

```bash
python benchmarks/run_quic_flow_comparison.py
python benchmarks/run_protocol_stream_accounting.py
python benchmarks/run_aioquic_workload_cases.py
python benchmarks/run_aioquic_scaling_experiment.py
python benchmarks/run_quic_miss_rate_sensitivity.py
python benchmarks/derive_deployment_envelope.py
```

The container fixes Python 3.12.13, pins Python dependencies, and fails its
build unless GNU rsync 3.2.7 is installed. The base-image digest and Debian OS
packages are not content pinned, so rsync protocol totals are version-recorded
measurements rather than a promise of byte-identical future container builds.
The CI reproduction gate permits a 1.0% difference in aggregate rsync
sent-plus-received protocol bytes. The maximum observed Ubuntu 24.04 difference
from the frozen environment was 0.591%, confined to sender-side control
overhead. Received bytes, literal and matched bytes, file-size counters, input
sizes, manifests, entry counts, reconstruction, round count, rsync 3.2.7, and
protocol version 31 remain exact. This tolerance is not statistical uncertainty
on the frozen result.
The pinned python-zstandard wheel reports libzstd 1.5.7 in the committed
baseline. The headline dictionary comparator pins level 3 and window_log 21;
every row also records a window_log 24 sensitivity result:

```bash
docker build -t redulink-artifact:v3.16 .
docker run --rm redulink-artifact:v3.16
```

## Evaluation boundary

Public object pairs are reproducible test artifacts, not sampled production
traffic. The Redis-derived layer case is author constructed and labeled as
such. Each reported stateful baseline must reconstruct exact bytes or an exact
ordered object/tree manifest. Multipliers always state their byte layer;
application-stream bytes are not presented as IP, UDP, or link-layer bytes.
