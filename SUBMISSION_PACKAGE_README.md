# ReduLink v3.8 submission package

Primary manuscript files:

- `paper/submission/ReduLink_journal_ready_v3_8.pdf`
- `paper/submission/ReduLink_journal_ready_v3_8.docx`

Quick validation:

```bash
python3 scripts/run_smoke_validation.py
```

For complete native QUIC validation, create a Python 3.10+ environment and run:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Full validation:

```bash
python3 scripts/run_full_validation.py
```

Aioquic-dependent tests skip gracefully when aioquic is absent. The v3.8
revision also includes `benchmarks/run_quic_miss_rate_sensitivity.py`, which
adds a small native QUIC miss-rate sensitivity sweep to the full-duplex path
emulation evidence.

The DOCX metadata identifies Michél Nguyen, University of the People, and ORCID 0000-0001-6834-4422. The package is intended to be clean of Python bytecode caches and platform metadata.

Scientific scope: ReduLink is evaluated as authenticated, scoped reference substitution over native QUIC streams. It is not claimed to be a custom QUIC extension-frame implementation, a replacement for rsync, or a universal compression substitute.
