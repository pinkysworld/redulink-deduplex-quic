# ReduLink journal-ready package v3.14 candidate

This is the reviewer-adapted v3.14 candidate of the ReduLink manuscript and
reproducibility artifact. It is based on public v3.13 commit
`dd7d52623b96af85e7e5ad19e587c060a3384b3a`; it is not yet a public v3.14 tag or
release. `SOURCE_GIT_STATUS.txt` records that distinction explicitly.

## Reviewer start here

1. Read `paper/submission/ReduLink_journal_ready_v3_14.pdf` or `.docx`.
2. Verify both against `MANUSCRIPT_SHA256.txt`.
3. Use `REVIEWER_RESPONSE_v3_14.md` to trace every v3.13 review finding.
4. Install `requirements-lock.txt` and run the smoke and full validators below.
5. Read `PUBLIC_REVIEWER_CHECKLIST.md` before checking public GitHub state.

Main files:

- DOCX: `paper/submission/ReduLink_journal_ready_v3_14.docx`
- PDF: `paper/submission/ReduLink_journal_ready_v3_14.pdf`
- Builder: `scripts/build_manuscript_v3_14.py`
- Figures: `scripts/make_journal_figures_v2_8.py`

## Claim boundary

ReduLink is endpoint-cooperative, scoped reference substitution for selected
warm-state transfers over QUIC streams. QUIC TLS/AEAD already supplies on-path
confidentiality and integrity. ReduLink's record HMACs bind dictionary epoch,
scope, stream, offset, nonce, identifier, length, and payload state after TLS;
they are intended to detect reference/dictionary-state confusion and fail closed,
not to claim a second independent defense against an on-path attacker.

The artifact is a compact binary application-stream mapping, not a custom QUIC
extension-frame implementation. Its native experiment verifies the ephemeral
server certificate but does not authenticate the client, and aioquic's public API
does not expose TLS exporter bytes. It therefore derives record keys from a fresh
private per-run exporter surrogate and random connection context; production
integration must use real exporter bytes.

ReduLink is not a universal accelerator or a replacement for gzip, zstd, rsync,
or HTTP Compression Dictionary Transport. RFC 9842 uses SHA-256 dictionary hashes,
same-origin/availability rules, and failure handling in an HTTP content-coding
deployment. The committed `zstd --patch-from` experiment is only a strong
whole-stream dictionary-delta byte baseline, not an implementation of RFC 9842.

## Validation

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
python3 scripts/run_smoke_validation.py
python3 scripts/run_full_validation.py
```

Both commands generate `data/target_corpora` before checking its hashes, so they
work from a clean clone. The smoke command checks core security, model, object,
wire, citation, and line-ending properties. Full validation runs every unittest
module in an isolated process. These commands validate committed results; they do
not silently rerun privileged network experiments or re-download all external
datasets.

Fetch the hash-pinned external public-release corpora when reproducing the
object-transfer suite:

```bash
python3 benchmarks/fetch_external_public_corpora.py
python3 benchmarks/run_external_object_workload_suite.py
```

The pinned container also installs zstd 1.5.7, GNU rsync, `tc/netem`, and
`taskset`:

```bash
docker build -t redulink-artifact:v3.14 .
docker run --rm redulink-artifact:v3.14
```

After a v3.14 release is actually published, its unauthenticated GitHub surfaces
can be checked with:

```bash
python3 scripts/verify_public_release.py --version 3.14
```

## Implemented evidence

- Plain and authenticated FULL/REF encode/decode models with fail-closed MISS
  repair, bounded replay state, independently checked offsets, and dictionary
  content revalidation.
- Bounded compact-binary messages over server-authenticated aioquic streams,
  including loss, repair, scaling, and dictionary-budget tests.
- Exact named-object reconstruction for public release and PyPI version pairs,
  including empty objects and authenticated object boundaries.
- Deterministic positive/negative fixtures, hash-pinned public pairs, real rsync,
  gzip/zstd, block-size, component-cost, framing, and miss-rate studies.
- Local 20-round userspace path emulation with paired completion ratios. The
  unshaped concurrent run is labeled a balance diagnostic, not fairness proof.
- A legacy v3.13 Linux `tc/netem` concurrent result, clearly marked as contention
  evidence. The corrected v3.14 runner defaults to isolated, order-alternated
  pairs and records command, host, tool, commit, and qdisc provenance. The manual
  `isolated Linux netem evidence` workflow executes that protocol in a dedicated
  Linux network namespace and uploads its raw JSON/CSV/log artifact. It still
  needs a successful run and result review before supporting isolated kernel-path
  latency claims.

Bootstrap intervals in the artifact describe variability among repeated local
runs. They are not WAN or deployment-population confidence intervals.
