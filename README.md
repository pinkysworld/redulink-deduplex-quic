# ReduLink v3.17 research artifact

ReduLink is a bounded reference-substitution codec for managed QUIC object
streams. The v3.17 paper is organized around three necessary deployment gates:

1. authorized exact state remains resident;
2. the transmitted representation preserves reusable byte boundaries; and
3. avoided literals exceed record, control, and repair cost.

The artifact is intentionally positive and negative. It shows where ReduLink
reduces bytes and completion time under aligned reuse, and where whole-layer
content addressing, rsync, ordinary compression, first-byte latency, or
fairness make it the wrong mechanism.

## Submission files

- Manuscript: `paper/submission/ReduLink_submission_v3_17.pdf` and `.docx`
- Highlights: `paper/submission/HIGHLIGHTS.txt`
- Reviewer-response map: `REVIEWER_RESPONSE_v3_17.md`
- Manuscript builder: `scripts/build_manuscript_v3_17.py`
- Figure builder: `scripts/make_submission_figures_v3_17.py`
- Manuscript hashes: `MANUSCRIPT_SHA256.txt`
- Evidence revision: `SOURCE_COMMIT.txt`
- Public checklist: `PUBLIC_REVIEWER_CHECKLIST.md`

## Evidence added in v3.17

- Complete analysis of the public IBM Docker Registry trace: 2,791 files and
  40,872,024 records across seven availability zones. The result is a
  same-client exact-blob LRU upper bound, not a measured client cache hit rate.
- Immutable Redis, httpd, and Alpine linux/amd64 registry-layer pairs. Existing
  whole-layer CAS hits are removed before testing changed compressed bytes at
  1, 4, and 16 KiB.
- Sixteen isolated Linux `tc/netem` path conditions with Reno, paired order,
  symmetric client-clock completion and FIRST_BYTE timing, combined endpoint
  CPU, exact reconstruction, and root-qdisc packet and byte deltas.
- Same-connection QUIC multistream isolation using live exporter keying and
  actual stream IDs 0, 4, 8, 12, and 16.
- Synchronized raw/raw, ReduLink/ReduLink, and calibrated raw/ReduLink competing
  flows with Jain fairness of encoded application goodput.
- Paired local CPU, completion, byte, and TTFB scaling from 64 KiB through
  32 MiB.

The record HMAC is defensive endpoint-state binding. QUIC/TLS is the network
security boundary. ReduLink is an application codec, not a custom QUIC frame.
The prototype uses a live TLS 1.3 exporter at both endpoints and aborts on
disagreement. Because aioquic 1.3.0 has no public exporter API, the audited
bridge is version gated.

## Claim boundary

The evidence supports the measured single-stack, single-host conditions and
the exact fixed artifacts. It does not establish Internet-wide latency,
multi-host deployment, independent-stack interoperability, 0-RTT, migration,
mutual application authentication, formal protocol composition, or an
optimized native implementation. The IBM trace lacks payload bytes; registry
alignment is therefore evaluated separately on pinned public blobs. The
Redis-derived transport fixture is author constructed and remains labeled as
such.

## Environment and validation

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
python scripts/run_smoke_validation.py
python scripts/run_full_validation.py
```

The validators check source ancestry, result schemas, exact reconstruction,
live exporter agreement, stream IDs, queue counters, citation coverage,
regenerated figures, normalized DOCX content, PDF claims, and manuscript
hashes.

## Regenerating the main v3.17 evidence

The IBM trace archive is not redistributed. After verifying and extracting the
published archive, run:

```bash
python benchmarks/run_ibm_registry_trace_residency_v3_17.py \
  --trace-root /path/to/extracted-trace \
  --archive /path/to/DockerRegistryTraces.tar.gz
```

The public registry-layer study retrieves immutable blobs into `/tmp` and
verifies their manifest digest, blob digest, and length:

```bash
python benchmarks/run_public_registry_layer_sensitivity_v3_17.py
```

The local implementation scaling study is:

```bash
python benchmarks/run_cpu_throughput_scaling_v3_17.py
```

The full privileged Linux path, multistream, and fairness experiments are
registered in `.github/workflows/linux-netem-isolated.yml`. The frozen full run
used the `full` profile, Reno, and source commit recorded in
`SOURCE_COMMIT.txt`. Local Linux reproduction requires an isolated namespace or
equivalent privileges:

```bash
python benchmarks/run_linux_netem_quic_path.py
python benchmarks/run_quic_multistream_experiment.py
python benchmarks/run_quic_competing_fairness_v3_17.py
```

Existing public-object, rsync, dictionary, capacity, and miss evidence can be
regenerated with the commands in `benchmarks/README.md`.

## Document production

```bash
python scripts/make_submission_figures_v3_17.py
python scripts/build_manuscript_v3_17.py
python scripts/check_manuscript_citations.py
python scripts/check_manuscript_hashes.py
```

The five figures are generated from committed results. Figure 1 uses separate
orthogonal MISSING and repair lanes so its labels remain readable at manuscript
size.
