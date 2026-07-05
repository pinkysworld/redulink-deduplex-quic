# Public Reviewer Checklist

Canonical artifact:

- Release/tag: `v3.12-journal-submission`
- Repository: `https://github.com/pinkysworld/redulink-deduplex-quic`
- Manuscript PDF: `paper/submission/ReduLink_journal_ready_v3_12.pdf`
- Manuscript DOCX: `paper/submission/ReduLink_journal_ready_v3_12.docx`

If a GitHub HTML page or raw CDN view appears stale, verify the immutable public
state through the GitHub API, tag dereference, or a fresh clone:

```bash
python3 scripts/verify_public_release.py --version 3.12
git ls-remote https://github.com/pinkysworld/redulink-deduplex-quic refs/heads/main refs/tags/v3.12-journal-submission
tmpdir=$(mktemp -d)
git clone --depth 1 https://github.com/pinkysworld/redulink-deduplex-quic "$tmpdir/repo"
grep -n "v3.12-journal-submission" "$tmpdir/repo/README.md"
rm -rf "$tmpdir"
```

Expected public state:

- `README.md`, `CITATION.cff`, `SOURCE_COMMIT.txt`, `SOURCE_GIT_STATUS.txt`,
  `pyproject.toml`, and `MANUSCRIPT_SHA256.txt` all name v3.12.
- `MANUSCRIPT_SHA256.txt` contains only v3.12 manuscript paths.
- `scripts/build_manuscript_v3_12.py` is the active manuscript builder.
- `scripts/check_text_line_endings.py` reports LF-only reviewer-facing text
  files.
- Kernel-path scripts are reviewer-runnable harnesses; the package does not
  claim completed live macOS dummynet, Linux `tc/netem`, Mininet, WAN, or
  production congestion-control evidence.
