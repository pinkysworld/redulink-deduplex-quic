# Comprehensive peer review and revision record — ReduLink v2.7 → v2.8

**Manuscript:** ReduLink: Authenticated Reference Substitution for Redundancy-Suppressed Transfers over Encrypted QUIC Streams
**Author:** Michél Nguyen (University of the People; ORCID 0000-0001-6834-4422)
**Version reviewed:** v2.7 (`ReduLink_journal_ready_v2_7.docx` / `.pdf` and the v2.7 reproducibility package)
**Target venue class:** strong applied networking / systems journal (e.g. IEEE/ACM ToN, IEEE TPDS, *Computer Networks*, IEEE Access)
**Reviewer role:** internal pre-submission peer review with verification of every quantitative claim and reference, followed by revision to v2.8.

---

## 1. Recommendation

**Minor revision (now applied in v2.8).** The work is well-scoped, intellectually honest, and unusually well-supported by a reproducible artifact. It does not over-claim, and it explicitly reports the (common) cases where simple baselines beat it. The issues found were limited to (a) one incorrect reference attribution, (b) a section-numbering defect, and (c) journal-readiness gaps (uncaptioned tables/figures, no keywords, no data-availability statement, no system diagram, no explicit research questions). None of these affect the validity of the results. All are addressed in v2.8.

The contribution is appropriate for an applied systems/networking journal **as a systems/measurement paper**, not as a new-algorithm paper — which is exactly how the authors frame it. For a top-tier venue (NSDI/SIGCOMM) the honest gaps (custom QUIC frame integration, live TLS-exporter keys, full congestion-control fairness study, a captured production trace) would still need to be closed; this is stated transparently in the Limitations section and is reaffirmed below.

## 2. Summary of the paper

ReduLink is an endpoint-controlled representation layer that replaces repeated payload chunks with compact **authenticated references** carried as compact binary records inside native (TLS-encrypted) aioquic QUIC streams. Each reference is bound by HMAC to epoch, scope, stream id, reconstructed offset, length, nonce, and chunk identity; non-validating references fail closed or trigger a semantic FULL-repair (MISS) path. The paper's claim is deliberately conditional: ReduLink helps for *warm-state, object-aligned or layer-like* encrypted transfers (registry/CDN/backup/update), and is explicitly **not** a replacement for rsync or compression on file-tree synchronization. Evaluation spans deterministic journal fixtures, external public source-release pairs (click/redis/nginx), object-aligned re-framings of the same public bytes, a Redis-derived layer-like positive case, native QUIC stream experiments (with periodic datagram loss), block-size sensitivity, component costs, repeated trials, and conservative wire-byte / accounting separation.

## 3. Strengths

1. **Intellectual honesty / claim boundary.** The paper states where it loses (rsync wins by up to 73× on source trees; compression/fixed reuse win on logs and package metadata) and frames the contribution as authenticated, scoped, stream-compatible substitution rather than superior matching. This is rare and valuable.
2. **Reproducibility.** The artifact runs end-to-end. A smoke command and a full-validation command are provided, the figures/tables regenerate from committed result files, and a citation checker is shipped.
3. **Security framing.** A concrete threat model (forgery, replay, dictionary poisoning, expansion abuse, content-existence leakage) is tied to specific artifact tests, and the dedup side-channel literature is correctly used to motivate dictionary scoping.
4. **Careful accounting.** The paper separates input / stream-payload / UDP-estimated byte layers and refuses to claim wire-rate acceleration or congestion credit for reconstructed bytes.

## 4. Verification performed (this review)

This was not a read-only review; every number and reference was checked against the artifact.

### 4.1 Quantitative integrity — PASS (no hallucinations found)
Every value in all 13 tables was cross-checked against the underlying result files. Representative checks:

| Manuscript claim | Source file | Status |
|---|---|---|
| disk snap 28.49× / fixed 31.97× | `results/journal_workload_suite.csv` | matches (28.487720 / 31.972680) |
| package meta RL 0.99× / fixed 9.88× / comp 14.31× | `results/journal_workload_suite.csv` | matches |
| redis source-release rsync 73.13× | `results/rsync_baseline_external_public.csv` | matches (73.134622) |
| object-aligned redis 9.70× / secure 9.04× / gzip 4.61× | `results/external_object_workload_suite.csv` | matches |
| layer-like redis 21.37× / 18.96× / 21.33× | `results/external_positive_suite.csv` | matches |
| block-size disk 1/2/4/8/16 KiB = 17.13/23.33/28.49/17.08/8.99× | `results/journal_block_size_sensitivity.csv` | matches |
| native QUIC raw/RL loss 0/9 UDP-est 0.90/2.60/0.78/2.38× | `results/quic_flow_comparison.csv` | matches |
| repeated trials raw client mean 227.04 ms (σ 19.90) | `results/repeated_quic_trials_summary.csv` | matches |
| component HMAC roundtrip 192.2 MiB/s | `results/component_performance.csv` | matches |

**Conclusion:** all sampled values, including every headline multiplier, reconcile to the committed data within rounding. No fabricated numbers were found. To keep it that way, every figure and table in v2.8 is regenerated by `scripts/build_manuscript_v2_8.py` and `scripts/make_journal_figures_v2_8.py` directly from the result files.

### 4.2 References — one error fixed, two enriched, all cited
- The automated checker confirms **18/18 references are cited** in the body.
- Spot-verified externally: refs [12] (arXiv:2409.06066) and [13] (arXiv:2504.02095) are real and correctly dated.
- **Defect (fixed):** ref [11] was attributed to "Y. Hu et al." The IEEE TPDS 2020 FastCDC paper "The Design of Fast Content-Defined Chunking for Data Deduplication **Based Storage Systems**" is first-authored by **Wen Xia** (vol. 31, no. 9, 2020). Corrected to the full Xia *et al.* author list with volume/number.
- arXiv identifiers added to [12]/[13]; canonical repository URLs added to [15] (ReduLink) and [18] (aioquic); the placeholder "J. B. P. et al." author for aioquic was replaced with "aioquic project contributors".

### 4.3 Reproducibility — PASS
- `python3 scripts/run_smoke_validation.py` → citation check OK, generated-artifact consistency OK, external object suite regenerated, unit subset OK.
- Full unit suite: **44 tests pass** (`python3 -m unittest discover -s tests`).

## 5. Major comments (and resolution in v2.8)

1. **Section-numbering defect.** In v2.7 the subsections "6.1–6.4" appeared *after* "7. Workload Results", so results subsections were mis-parented to the Methodology section. **Resolved:** renumbered to **7.1–7.4** under "7. Workload Results and Baseline Interpretation".
2. **No system/architecture figure.** A systems paper needs one canonical picture of sender → chunker → FULL/REF decision → encrypted QUIC stream → receiver validation/reconstruction → MISS-repair loop. **Resolved:** added **Figure 1** (`figures/architecture/redulink_architecture.png`).
3. **No explicit research questions.** **Resolved:** added RQ1–RQ3 to the Introduction, which the evaluation already answers.
4. **Tables/figures lacked numbers and captions** (13 unlabeled tables, 2 loosely-labeled figures) — a hard requirement for journal copy-editing and cross-referencing. **Resolved:** all tables are now **Table 1–13** with descriptive captions; figures are **Figure 1–4** with captions; a block-size **Figure 4** was added to complement Table 8.

## 6. Minor comments (and resolution)

- **Abstract** lacked a quantitative headline. Added one sentence with the verified positive range (1.94–9.70×, up to 21.37×) and the negative rsync result (up to 73×).
- **Keywords/index terms** were missing. Added.
- **Data and Code Availability** statement was missing (standard for reproducible journals). Added, pointing at the repository and the MIT license, and noting corpora are reconstructed from public sources rather than redistributed.
- **Page numbers** were absent. Added a page-number footer.
- Author identity, affiliation, and ORCID were left unchanged by design.

## 7. Remaining limitations (correctly disclosed; not blockers for the target venue)

These are stated in §12 and are reaffirmed here as the honest gap to a top-tier networking venue:
1. Native mapping uses **QUIC streams, not custom QUIC extension frames / transport parameters**.
2. The key schedule is an **exporter-style model**, not live QUIC TLS exporter bytes.
3. Object-aligned and layer-like workloads are **transfer-model experiments over real public bytes**, not a captured production registry/backup trace.
4. Fairness evidence is conservative wire-byte accounting and bottleneck emulation, **not a full tc/netem or Mininet congestion-control study**.

Closing any one of these (most valuably #1 or #3) is the recommended next research step.

## 8. Changelog v2.7 → v2.8

- Fixed section numbering (6.1–6.4 → 7.1–7.4).
- Corrected reference [11] author attribution; enriched [11],[12],[13],[15],[18].
- Added Figure 1 (architecture) and Figure 4 (block-size sensitivity); renumbered the two existing figures.
- Added captions/numbers to all tables (1–13) and figures (1–4).
- Added research questions (RQ1–RQ3), a quantitative abstract sentence, a Keywords line, a Data and Code Availability section, and page numbers.
- All numbers regenerated from committed result files; 44/44 tests and the citation checker pass on the revised manuscript.
