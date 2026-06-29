# Second-round peer review — ReduLink v2.8

**Manuscript:** ReduLink: Authenticated Reference Substitution for Redundancy-Suppressed Transfers over Encrypted QUIC Streams
**Version reviewed:** v2.8 (the peer-review-adapted revision)
**Target venue class:** strong applied networking / systems journal (IEEE/ACM ToN, IEEE TPDS, *Computer Networks*, IEEE Access)
**Reviewer role:** independent second-round review with fresh scrutiny, including verification that the v2.8 edits did not introduce regressions.

---

## 1. Recommendation

**Minor revision.** The round-1 defects are resolved and the paper reads cleanly. The numbers remain fully reconciled to the artifact, the section numbering is fixed, and the new figures/captions/keywords/data-availability material is in place. Two things keep this from being an immediate accept: **(M1)** the related-work section omits the closest existing line of work (HTTP shared-dictionary / delta transport, including a 2024 standard that runs over QUIC), which a reviewer will read as a novelty gap; and **(M2/M3)** two presentation defects — figures numbered out of order and no in-text references to any table or figure. M1 is the only one that touches the scientific argument; the rest are mechanical.

## 2. Confirmation that round-1 fixes hold (and no regressions)

- **Numbers still clean.** The v2.8 additions reconcile to the data: object-aligned ReduLink 1.94×/4.38×/9.70×, layer-like 21.37×, max rsync 73.13× — exactly as stated in the new abstract sentence. No fabricated values were introduced.
- **Citations:** checker still reports 18/18 cited; the corrected [11] (W. Xia) and enriched [12]/[13]/[15]/[18] are in place.
- **Structure:** results subsections are now 7.1–7.4; no dangling "6.x" cross-references remain.

## 3. Major comment

### M1 — Missing the closest related work: HTTP shared-dictionary / delta transport
The paper positions ReduLink against in-network RE (Spring/Wetherall, SmartRE, EndRE), file-delta systems (rsync/LBFS), and CDC/dedup security. It does **not** mention the HTTP/web lineage of *receiver-side dictionary referencing over encrypted transport*, which is conceptually the nearest neighbour:

- **RFC 3229 — Delta encoding in HTTP** (with **VCDIFF**, RFC 3284): send only the delta of a response relative to a prior instance the client already holds.
- **SDCH (Shared Dictionary Compression over HTTP)**: Google's deployed shared-dictionary-over-HTTP scheme.
- **RFC 9842 — Compression Dictionary Transport** (Shared Brotli / Shared Zstandard; shipped in Chrome 130, Oct 2024): designates a previously fetched HTTP response as an external dictionary so future responses are delta-compressed against receiver-held bytes. Because it operates on HTTP responses, **it already runs over HTTP/3-on-QUIC** — i.e. receiver-side dictionary referencing over an encrypted QUIC-based transport, which is precisely ReduLink's setting.

This is important because a reviewer will ask, *"how is this different from Compression Dictionary Transport?"* The answer exists in the paper's design but is never stated as a contrast. ReduLink's genuine differentiators are: (a) **per-reference authenticated context binding** (epoch/scope/stream/offset/length/nonce/chunk-id under HMAC) and **fail-closed** semantics, versus CDT/SDCH which rely on the surrounding TLS channel for integrity and treat the dictionary as a codec input; (b) an explicit **semantic MISS/FULL repair** path; and (c) a **general stream-representation** abstraction rather than a codec scoped to HTTP responses with `Use-As-Dictionary` matching. 

*Action:* add a short related-work paragraph (3 references: RFC 3229/VCDIFF, SDCH, RFC 9842) that names CDT explicitly and states the authentication / fail-closed / repair distinctions. This both closes the gap and strengthens the novelty claim. It does not require new experiments, though a sentence acknowledging that CDT is the strongest deployed baseline would be candid and on-brand for this paper.

## 4. Moderate comments (presentation defects)

### M2 — Figures are numbered out of order
Figures appear in document order **1, 2, 4, 3**: the block-size figure is labelled **Figure 4** in §7.4 but precedes the native-QUIC **Figure 3** in §8. Floats must be numbered in order of first appearance. *Action:* relabel the block-size figure as **Figure 3** and the native-QUIC figure as **Figure 4** (and update their captions accordingly). (Note: this defect was introduced during the v2.8 revision when the block-size figure was added.)

### M3 — No in-text cross-references to tables or figures
None of the 13 tables or 4 figures is referenced from the body prose; they appear only as captioned floats. Journal style (and copy-editing) requires each float to be cited in the text where it is discussed — e.g. "Table 4 reports the warm-state workloads…", "the architecture is shown in Figure 1", "Figure 2 plots the object-aligned multipliers." *Action:* add a cross-reference for each table and figure at its point of discussion. Low effort, but expected.

## 5. Minor comments

- **m1 — Test environment unspecified.** Absolute timings (raw client 227 ms, ReduLink 137 ms; component throughputs in MiB/s) are reported without a stated machine (CPU model, core count, RAM, OS, Python/aioquic build). Add a one-line environment description in §5 or §9 so the "local" timings are interpretable and reproducible; otherwise they are not comparable across reviewers' machines.
- **m2 — n = 3 repeated trials is thin.** The std-dev table is appropriate and the paper correctly notes the multiplier is deterministic, so only elapsed time varies. Still, raising the timing trials to n ≥ 10 (cheap, loopback) would make the variance estimate meaningful rather than indicative.
- **m3 — Loopback-only transport.** All QUIC experiments run over localhost with an artificial periodic-drop proxy; there is no RTT/bandwidth/real-loss diversity. This is disclosed in §12, but even a single tc/netem emulated-RTT-and-bandwidth point would materially strengthen the transport story and partially address the fairness limitation already flagged as future work.
- **m4 — Figure 1 legibility.** The dashed red "MISS / request semantic FULL repair" arrow overlaps the "Reference decision" box; nudging the arc or the label would improve readability.
- **m5 — Abstract length.** Now three paragraphs plus keywords; the methods sentence ("The artifact maps… conservative fairness accounting") could be tightened. Optional.
- **m6 — Byline.** The author line carries "minh.systems" alongside the institutional affiliation; confirm the target venue accepts a personal domain in the affiliation block (many want institution + email only).

## 6. Summary of requested changes

| # | Severity | Change | Effort |
|---|---|---|---|
| M1 | Major | Add related-work paragraph + 3 refs (RFC 3229/VCDIFF, SDCH, RFC 9842 CDT); differentiate ReduLink | ~half a page, no experiments |
| M2 | Moderate | Swap Figure 3 ↔ Figure 4 so figures are in appearance order | trivial |
| M3 | Moderate | Add in-text references to all tables and figures | low |
| m1 | Minor | State the timing test environment | trivial |
| m2 | Minor | Increase repeated-trial n (optional) | low |
| m3 | Minor | Add one emulated-RTT/bandwidth transport point (optional, strong upside) | medium |
| m4–m6 | Minor | Figure-1 arrow polish; abstract trim; byline check | trivial |

Only M1 affects the scientific argument; M2/M3 are required for journal copy-editing; the rest are improvements. With M1–M3 addressed, the paper is in good shape for the target venue class.
