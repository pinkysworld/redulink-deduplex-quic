# Manuscript files

The active submission files are:

- `paper/submission/ReduLink_submission_v3_17.docx`
- `paper/submission/ReduLink_submission_v3_17.pdf`

Regenerate the five figures and editable manuscript from committed evidence:

```bash
python scripts/make_submission_figures_v3_17.py
python scripts/build_manuscript_v3_17.py
```

Validate references, hashes, synchronized evidence, and fixed-layout claims:

```bash
python scripts/check_manuscript_citations.py
python scripts/check_manuscript_hashes.py
python scripts/check_submission_evidence.py
```

The v3.17 manuscript reports production-trace residency bounds, immutable
compressed-layer alignment, deterministic byte economics, and controlled
single-host QUIC path, stream, fairness, and Python CPU measurements. Earlier
asymmetric-clock timing and userspace path-emulation outputs are excluded.
