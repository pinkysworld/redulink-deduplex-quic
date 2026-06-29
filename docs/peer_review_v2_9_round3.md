# Third-round peer review — ReduLink v2.9 (adapted into v3.0)

**Version reviewed:** v2.9 (the expanded revision)
**Outcome version:** v3.0 (valid outcomes applied)
**Target venue class:** strong applied networking / systems journal
**Reviewer role:** third-round review, focused on whether the v2.9 expansion introduced new defects, on presentation fairness of the newly added tables, and on the accuracy of the newly added references.

---

## 1. Recommendation

**Accept with minor revision — the paper has converged.** The v2.9 expansion is sound: no new numeric errors were introduced, every table and figure number reconciles to the committed data, and the four newly added references are accurate (RFC 9842 verified as Meenan & Weiss, published 2025). The third round surfaced only one worthwhile structural addition and one minor presentation clarification, both now applied in v3.0. The remaining open items are the previously disclosed gaps that require new experiments, not further review.

## 2. Verification of the v2.9 expansion (no regressions)

- The new inline and tabular numbers in the fairness section (wire shares 0.083/0.917, Jain indices 0.919/0.914, bottleneck completion 29.7/51.3 ms and goodputs) reconcile exactly to `results/quic_competing_flows.json`, `results/wire_fairness_accounting.json`, and `results/quic_bottleneck_emulation.csv`. The scaling and repair tables likewise match their result files.
- New references checked: RFC 3229 (delta encoding), RFC 3284 (VCDIFF), SDCH (Internet-Draft), and RFC 9842 (Compression Dictionary Transport, P. Meenan and Y. Weiss, 2025) are all real and correctly attributed.
- Structure: 19 tables and 4 figures, all numbered in appearance order and all cross-referenced in the body; sections 1-15 are contiguous; the citation checker reports 22/22.
- No unverifiable shipping-date claims appear in the body.

## 3. Findings and disposition

### R3-1 (structural, applied) — Positioning/comparison table
The round-2 related-work addition (Section 3.3) differentiates ReduLink from HTTP shared-dictionary transport in prose, but a reviewer assessing novelty benefits from a single consolidated comparison. *Applied in v3.0:* added Table 20 in Section 12, contrasting ReduLink with in-network RE, rsync/LBFS, HTTP shared-dictionary/CDT, and local compression across five dimensions (operation over E2E-encrypted transport, per-reference authentication, fail-closed repair, receiver dictionary, best-fit workload), with a forward pointer from Section 3.3. This crystallizes that ReduLink is the only listed approach combining an encrypted QUIC stream with per-reference authentication and explicit fail-closed repair.

### R3-2 (minor, applied) — Bottleneck-table goodput labels
In the bottleneck emulation (Table 18) the columns compared "Raw goodput" with "RL reconstructed goodput," which could read as apples-to-oranges. Because both flows deliver the identical 98,304 application bytes, the comparison is in fact a like-for-like application-goodput comparison. *Applied in v3.0:* relabeled both columns as application goodput and added a clause stating that the application bytes are held constant, so the columns are directly comparable.

### R3-3 (minor, not applied) — Abstract length
The abstract is three paragraphs. This is on the longer side but within range for an applied systems journal and is informative; trimming risks losing the quantitative summary. Left as-is; a venue-specific copy-edit can shorten it if the target journal imposes a word cap.

## 4. Remaining gaps (unchanged; require new experiments, not review)

These were disclosed in round 1 and remain the honest path to a top-tier venue; none is a correctness problem:
1. QUIC stream mapping rather than custom QUIC extension frames / transport-parameter negotiation.
2. Exporter-style key schedule rather than live QUIC TLS exporter bytes.
3. Transfer-model and fluid-emulation evidence rather than captured production traces and a full tc/netem or Mininet congestion-control study over real paths.
4. A quantitative head-to-head against Compression Dictionary Transport on the same corpora (now explicitly listed as future work).

## 5. Note on convergence

Three review rounds have taken the manuscript from a defect-bearing draft (incorrect citation, section-numbering bug, missing related work, thin evidence) to a complete, internally consistent, reproducible paper with a clear claim boundary. Further improvement is now bounded by new experimental work rather than by additional review. I recommend proceeding to venue-specific formatting and submission.
