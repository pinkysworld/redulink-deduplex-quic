# ReduLink v3.9 submission package

Primary manuscript files:

- `paper/submission/ReduLink_journal_ready_v3_9.pdf`
- `paper/submission/ReduLink_journal_ready_v3_9.docx`

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

Aioquic-dependent tests skip gracefully when aioquic is absent. The v3.9
revision refreshes the repeated local QUIC evidence at 20 rounds per reported
grid point and includes both macOS pf/dnctl and Linux `tc/netem` kernel-path
harnesses. The kernel harnesses are reviewer-runnable infrastructure; no live
kernel-path aioquic result is claimed in this package.

The DOCX metadata identifies Michél Nguyen, University of the People, and ORCID 0000-0001-6834-4422. The package is intended to be clean of Python bytecode caches and platform metadata.

Scientific scope: ReduLink is evaluated as authenticated, scoped reference substitution over native QUIC streams. It is not claimed to be a custom QUIC extension-frame implementation, a replacement for rsync, or a universal compression substitute.
