# Revision history (factual changelog)

- v3.11: public-GitHub hygiene cleanup after a reviewer found raw-view
  formatting problems: reviewer-facing Markdown/CSV/JSON/script metadata is
  normalized to LF line endings, CSV writers now force LF output, smoke/full
  validation and CI include a tracked text line-ending guard, and the package is
  republished as the latest GitHub release without changing the v3.10 tag.

- v3.10: consistency-focused cleanup before submission: stale abstract and
  Section 8.2/Table 15 wording are aligned with the n=20 QUIC evidence; package
  metadata is promoted in `pyproject.toml`; the PyPI evidence is named as a
  version-pair object study rather than a trace; a lockfile and Dockerfile give
  an exact dependency path; Section 10 adds an explicit "what this does not
  prove" scope note; and the security table separates specified, implemented,
  tested, and future-work items.

- v3.9: package metadata, manuscript filenames, citation metadata, and build
  script names are promoted consistently from v3.8 to v3.9; repeated local QUIC
  evidence is refreshed at 20 rounds for the path-emulation grid, concurrent
  localhost pair, and sequential QUIC repeats; bootstrap confidence intervals
  are regenerated; and a Linux `tc/netem` kernel-path harness is added alongside
  the macOS dummynet harness. The package still does not claim a completed live
  kernel-path aioquic sweep.

- v3.8: external-review cleanup for journal submission: GitHub-facing package
  metadata is made self-consistent; `SOURCE_GIT_STATUS.txt` now points to the
  current release tag rather than v3.6; reviewer-start/environment guidance is
  added; the isolated unittest runner no longer depends on GNU `timeout`; and a
  native QUIC miss-rate sensitivity sweep varies semantic misses from about 1%
  to 49% at 5 Mbps and 20 ms RTT, showing the stream multiplier falling from
  5.75x to 1.48x and the completion-time advantage narrowing.

- v3.7: path emulator corrected to a full-duplex per-direction token bucket
  (fixes a half-duplex artifact that had wrongly shown ReduLink ~74% slower);
  on byte-stable content ReduLink now completes in 0.65x of raw on a constrained
  link, while a real Redis-layered payload (72 misses) can run 1.11-1.27x slower
  where repair round trips dominate. Table 20 adds dispersion (s.d.) and both
  payloads. Emulation is explicitly emulation-model-dependent pending a kernel
  emulator.

- v3.6: authentication-first verification with a bounded replay window; UDP
  prototype binds expected offsets to sequence numbers and returns uniform
  on-wire validation errors; CI fetches corpora before unit tests and the
  corpora-dependent test/smoke steps skip cleanly when data is absent;
  framing repricing (measured 108 B/frame) and a zstd --patch-from
  dictionary-delta baseline added (Sec. 7.6, Table 12); offline-vs-QUIC gap
  reconciled (Sec. 8.1); keying per artifact path stated precisely; stale
  result generations regenerated consistently; committed evidence uses
  repo-relative paths; historical build scripts and review notes pruned.
- v3.5: 16 MiB scaling with dictionary-budget overflow (0.92x fail-safe) and
  recovery (3.96x at 24,576 chunks); release-pinned artifact citation.
- v3.4: measured userspace path emulation (byte savings do not imply
  completion-time savings for small repair-bearing transfers); byline cleanup.
- v3.3: fixture unchanged-fractions disclosed; analytic bottleneck model
  labeled as computed; security evidence scoped; identifier sizing guidance.
- v3.2: PyPI version-pair study; 12-round measured competing flows; formal
  security model and reduction sketch (Sec. 4.5).
- v3.0-v3.1: positioning table; measured-vs-model labeling; strict-review
  disclosures.
- v2.7-v2.9: journal-ready consolidation; HTTP delta / shared-dictionary
  related work; figures, captions, and cross-references.
