# Reviewer Checklist

Local reviewer-adapted candidate:

- Candidate version: `v3.14-reviewer-adapted-candidate`
- Base commit: `dd7d52623b96af85e7e5ad19e587c060a3384b3a`
- Repository: `https://github.com/pinkysworld/redulink-deduplex-quic`
- Manuscript PDF: `paper/submission/ReduLink_journal_ready_v3_14.pdf`
- Manuscript DOCX: `paper/submission/ReduLink_journal_ready_v3_14.docx`
- Finding-by-finding response: `REVIEWER_RESPONSE_v3_14.md`

This working tree is not yet a public v3.14 release. Do not treat a failed
public-release lookup as an artifact failure until the candidate is committed,
tagged, and published. The last immutable public snapshot remains v3.13.

Local validation from a clean clone or exported candidate:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
python3 scripts/run_smoke_validation.py
python3 scripts/run_full_validation.py
```

Both validators generate the gitignored deterministic target corpora before
checking their hashes. External public-release corpora are fetched separately
with `python3 benchmarks/fetch_external_public_corpora.py`.

After v3.14 is published, verify its immutable public state with:

```bash
python3 scripts/verify_public_release.py --version 3.14
git ls-remote https://github.com/pinkysworld/redulink-deduplex-quic refs/heads/main refs/tags/v3.14-journal-submission
```

Expected candidate coherence:

- Metadata, manuscript paths, active builder, and hashes all name v3.14.
- `SOURCE_GIT_STATUS.txt` identifies the candidate review branch and states
  that it is not yet the immutable public v3.14 tag/release.
- `scripts/check_text_line_endings.py` reports LF-only reviewer-facing text.
- The legacy v3.13 Linux netem result is labeled as concurrent contention
  evidence; the v3.14 runner defaults to isolated, order-alternated pairs and
  records tool, command, commit, and qdisc provenance.
