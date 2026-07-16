# ReduLink v3.17 submission package

Primary manuscript files:

- `paper/submission/ReduLink_submission_v3_17.pdf`
- `paper/submission/ReduLink_submission_v3_17.docx`
- `paper/submission/HIGHLIGHTS.txt`
- `MANUSCRIPT_SHA256.txt`

`SOURCE_COMMIT.txt` records the experiment revision. The registered full Linux
workflow artifacts identify the same commit. Reproducibility commands, claim
boundaries, and result paths are listed in `README.md`,
`benchmarks/README.md`, `paper/evidence_tables.md`, and
`PUBLIC_REVIEWER_CHECKLIST.md`.

Run the complete nonprivileged validation from a clean clone:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
python scripts/run_full_validation.py
```

Scientific scope: ReduLink is a QUIC application-stream mapping for explicit
warm-state references with bounded receive invariants and batched repair. The
submission evaluates three independent gates: authorized residency,
representation alignment, and byte economics. It includes production-trace
residency bounds, immutable compressed-layer alignment, controlled Linux
completion and TTFB, multistream isolation, competing-flow fairness, and local
CPU scaling.

The package does not claim a production deployment, multi-host Internet
performance, independent-stack interoperability, formal protocol composition,
0-RTT or migration support, or optimized native throughput.
