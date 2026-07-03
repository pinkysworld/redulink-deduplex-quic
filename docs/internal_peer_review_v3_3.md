# Internal peer review notes for v3.3

Version 3.3 adapts the round-5 fresh review (`docs/peer_review_v3_2_round5.md`)
and an external reviewer's report on the v3.2 paper + public repository.

## Adapted
- R5-1: Section 7.5 now disclosed as a modeled file-granular registry channel
  (PyPI serves single compressed wheel archives today; gzip baseline runs on the
  uncompressed object stream).
- R5-2: proof sketch corrected — a wrong-bytes REF needs a collision either in
  SHA-256 or in the 128-bit truncated identifier (birthday-bounded), not
  "ultimately a SHA-256 collision".
- R5-3: theorem scope stated (manifest-mode dictionary safety specified, not
  analyzed).
- R5-4: Jain-index two-flow scale note (0.5-1.0) added.
- R5-5: `paper/evidence_tables.md` regenerated with current version header via
  the generator script; evidence hierarchy refreshed (`evidence_hierarchy_v3_3.md`).
- External S6a: Section 4.3 identifier prose aligned with the artifact formula
  in Section 4.5 (epoch + scope + chunk-hash in the artifact; stream/length in
  the frame tag; spec profile may bind more).
- External S6b: identifier sizing guidance added (collision probability at 2^30
  and 2^40 entries; 192/256-bit recommendation for very large dictionaries).
- External repo-sync findings: version metadata, hashes, README, CITATION.cff
  all bumped to v3.3; annotated submission tag created.

## Not adaptable from this environment
- GitHub "About" description still says "effective bandwidth expansion" - it is
  repository metadata, editable only via github.com settings.
- GitHub Release + Zenodo DOI require web/API access; the annotated git tag
  `v3.3-journal-submission` is prepared for it.

## Verification
Citation checker 25/25; tables 1-21 ordered; all new numbers verified; full
suite 45 tests (1 environment skip).
