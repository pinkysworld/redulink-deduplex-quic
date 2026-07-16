# Manuscript files

The active submission files are:

- `paper/submission/ReduLink_journal_ready_v3_16.docx`
- `paper/submission/ReduLink_journal_ready_v3_16.pdf`

Regenerate the figures and manuscript after regenerating the committed results:

```bash
python scripts/make_journal_figures_v3_16.py
python scripts/build_manuscript_v3_16.py
```

Validate references, file hashes, and layout before distribution:

```bash
python scripts/check_manuscript_citations.py
python scripts/check_manuscript_hashes.py
```

The manuscript reports exact reconstruction and application-stream byte counts.
Historical timing, path-emulation, and competing-flow outputs are not included
in the submission evidence.
