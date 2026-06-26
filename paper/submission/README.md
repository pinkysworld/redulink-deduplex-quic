# Submission Artifacts

Current v0.9 submission-ready draft:

- `ReduLink_full_draft_v0_9_submission_ready.docx`
- `ReduLink_full_draft_v0_9_submission_ready.pdf`

This version synchronizes the manuscript with:

- deterministic target-class evidence,
- renamed compressed-related and independent-compressed negative controls,
- public-corpus fixture limits,
- corrected socket prototype byte accounting,
- package-safe test behavior,
- wall-clock cost-column naming,
- candidate Deduplex-QUIC profile language.

Prior drafts retained for comparison:

- `ReduLink_Deduplex_QUIC_full_draft_v0_8_peer_review_strengthened.docx`
- `ReduLink_Deduplex_QUIC_full_draft_v0_8_peer_review_strengthened.pdf`
- `ReduLink_Deduplex_QUIC_full_draft_v0_7_public_corpora_rsync_prototype.docx`
- `ReduLink_Deduplex_QUIC_full_draft_v0_7_public_corpora_rsync_prototype.pdf`

The runnable evidence behind the draft is kept in the repository root:

- `benchmarks/` fetches/generates and evaluates synthetic, public-fixture, and target-class workloads.
- `results/` contains generated CSV result tables and metadata sidecars.
- `figures/` contains generated paper-facing plots and summaries.
- `prototypes/` contains the minimal localhost reconstruction prototype.
- `tests/` contains reconstruction, safety, accounting, plotting, and prototype tests.
