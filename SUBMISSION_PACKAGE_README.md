# ReduLink v3.12 submission package

Primary manuscript files:

- `paper/submission/ReduLink_journal_ready_v3_12.pdf`
- `paper/submission/ReduLink_journal_ready_v3_12.docx`

Quick validation:

```bash
python3 scripts/run_smoke_validation.py
```

This includes the raw-public text line-ending check
(`python3 scripts/check_text_line_endings.py`) so reviewer-facing Markdown and
CSV files stay LF-only in GitHub Raw views.

If GitHub HTML or raw CDN views appear stale, use the public-state checklist and
API/raw verifier:

```bash
python3 scripts/verify_public_release.py --version 3.12
```

For complete native QUIC validation, create a Python 3.10+ environment and run:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

For exact dependency reproduction, use `requirements-lock.txt` instead of
`requirements-dev.txt`, or build and run the pinned container:

```bash
docker build -t redulink-artifact:v3.12 .
docker run --rm redulink-artifact:v3.12
```

Full validation:

```bash
python3 scripts/run_full_validation.py
```

Aioquic-dependent tests skip gracefully when aioquic is absent. The package
includes repeated local QUIC evidence at 20 rounds per reported grid point and
both macOS pf/dnctl and Linux `tc/netem` kernel-path harnesses. The kernel
harnesses are reviewer-runnable infrastructure; no live kernel-path aioquic
result is claimed in this package.

The DOCX metadata identifies Michél Nguyen, University of the People, and ORCID 0000-0001-6834-4422. The package is intended to be clean of Python bytecode caches and platform metadata.

Scientific scope: ReduLink is evaluated as authenticated, scoped reference substitution over native QUIC streams. It is not claimed to be a custom QUIC extension-frame implementation, a replacement for rsync, or a universal compression substitute.
