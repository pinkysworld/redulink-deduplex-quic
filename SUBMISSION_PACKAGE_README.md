# ReduLink v2.9 submission package

Primary manuscript files:

- `paper/submission/ReduLink_journal_ready_v2_9.pdf`
- `paper/submission/ReduLink_journal_ready_v2_9.docx`

Quick validation:

```bash
python3 scripts/run_smoke_validation.py
```

Full validation:

```bash
python3 scripts/run_full_validation.py
```

The DOCX metadata identifies Michél Nguyen, University of the People, and ORCID 0000-0001-6834-4422. The package is intended to be clean of Python bytecode caches and platform metadata.

Scientific scope: ReduLink is evaluated as authenticated, scoped reference substitution over native QUIC streams. It is not claimed to be a custom QUIC extension-frame implementation, a replacement for rsync, or a universal compression substitute.
