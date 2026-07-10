# ReduLink v3.14 reviewer-adapted candidate

Primary manuscript files:

- `paper/submission/ReduLink_journal_ready_v3_14.pdf`
- `paper/submission/ReduLink_journal_ready_v3_14.docx`
- `REVIEWER_RESPONSE_v3_14.md` maps every review finding to its disposition.

Pinned reviewer validation:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
python3 scripts/run_smoke_validation.py
python3 scripts/run_full_validation.py
```

The validators recreate gitignored deterministic target fixtures, so both work
from a clean clone. Full validation executes all test modules; it validates
committed experiment evidence but does not rerun privileged kernel-path sweeps.

The container pins Python packages, zstd 1.5.7, GNU rsync, and the Linux
`tc/netem` and CPU-affinity tools used by the experiment harnesses:

```bash
docker build -t redulink-artifact:v3.14 .
docker run --rm redulink-artifact:v3.14
```

This tree is a local candidate based on v3.13, not yet a public v3.14 tag or
release. After publication, run `python3 scripts/verify_public_release.py
--version 3.14` to check the unauthenticated GitHub surfaces.

Scientific scope: ReduLink is authenticated, scoped reference substitution over
native QUIC streams. It is not a custom QUIC frame implementation, a universal
compression replacement, or a demonstrated WAN/fairness result. The legacy
kernel run was concurrent; the corrected runner provides isolated paired runs.
