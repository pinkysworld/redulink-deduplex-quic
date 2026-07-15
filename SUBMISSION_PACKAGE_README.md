# ReduLink v3.15 submission package

Primary manuscript files:

- `paper/submission/ReduLink_journal_ready_v3_15.pdf`
- `paper/submission/ReduLink_journal_ready_v3_15.docx`
- `paper/submission/HIGHLIGHTS.txt`
- `MANUSCRIPT_SHA256.txt`

The source revision used to generate the packaged evidence is recorded in
`SOURCE_COMMIT.txt`. Reproducibility commands, evidence boundaries, and exact
result paths are listed in `README.md`, `benchmarks/README.md`, and
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
submission reports exact reconstruction and same-layer protocol-stream byte
counts. It does not report WAN latency, congestion fairness, or production
throughput.
