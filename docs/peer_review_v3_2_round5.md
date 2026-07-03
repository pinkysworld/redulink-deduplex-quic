# Fresh peer review (round 5) — ReduLink v3.2 package

**Version reviewed:** v3.2 (manuscript `ReduLink_journal_ready_v3_2.pdf/.docx` + full artifact at commit `9cc7e21`)
**Reviewer posture:** fresh eyes on the whole package, with focused scrutiny on the three components added in v3.2 (formal security analysis §4.5, independent PyPI trace §7.5, measured competing-flow fairness §10).

---

## 1. Recommendation

**Accept with minor revision.** The v3.2 additions substantially close the gaps the strict round-4 review identified, and they survive re-verification: the full test suite passes (45 tests, 1 benign skip for unfetched corpora), the citation checker reports 25/25, all 21 tables and 4 figures are numbered in strict appearance order and every one is referenced in prose, and both new results tables reconcile exactly to the committed result files. The remaining findings are one genuine methodology-disclosure gap in the new trace, two precision issues in the new security section, one metric-interpretation note, and package housekeeping. None requires new experiments.

## 2. Re-verification performed (all pass)

- Full unit suite: 45 tests OK (1 skip: public-corpora fixture not fetched in this environment — the skip message correctly instructs how to enable it).
- Citations 25/25; references [23]–[25] (HMAC, HKDF, Jain) correctly support the new sections.
- Table captions appear in strict increasing order 1–21; figure captions 1–4; no orphan or unreferenced floats — the v3.2 renumbering introduced no defects.
- Table 11 (PyPI trace) reconciles row-for-row with `results/pypi_object_trace.csv`, including file-stability counts; wheels are SHA-256-pinned in the CSV. Table 18 reconciles with `results/quic_competing_flows.json` (12 rounds, reconstructed-rate Jain 0.923, encoded-rate 0.722).
- §4.5 and §7.5 render cleanly and are internally consistent with Table 3's artifact-status caveats.

## 3. Findings

### R5-1 (moderate) — The PyPI trace models a file-granular registry, which is not how PyPI serves packages today
§7.5 is the paper's strongest external positive evidence, and its data is genuinely independent. But the transfer model deserves one more sentence of honesty: a real `pip install` downloads a **single compressed wheel archive (a zip)**, not the wheel's member files as individually addressable objects. The trace therefore measures real bytes and real cross-version overlap under a *modeled file-granular object channel* — a registry serving per-file objects with a warm client dictionary — not pip's current wire format; deploying ReduLink for this use case would require registry-side changes. Relatedly, the gzip baseline is computed over the **uncompressed** object stream, while production wheels are already deflate-compressed in transit; the comparison is internally consistent across methods, but a reader mapping the numbers onto today's PyPI could be misled. *Action:* add 1–2 disclosure sentences to §7.5. This does not weaken the trace's role (the object-channel model is exactly the paper's stated deployment class, and §7.2 uses the same abstraction), but it must be said.

### R5-2 (minor) — Proof-sketch imprecision on identifier collisions
§4.5's sketch says a REF resolving to wrong bytes requires "a collision in the keyed identifier and **ultimately a SHA-256 collision**." Not quite: because the identifier is truncated to 128 bits, two distinct chunks can collide in the truncated MAC output **without** any SHA-256 collision (birthday bound ~2^64, which the caveat paragraph itself acknowledges). The sketch and the caveat are currently slightly inconsistent. *Action:* reword to "a collision either in SHA-256 or in the 128-bit truncated identifier; the former contradicts collision resistance, the latter is birthday-bounded as discussed below."

### R5-3 (minor) — Theorem scope narrower than the stated goals
§4.5 states four security goals, but the theorem covers reference unforgeability and context binding (with replay and expansion argued in passing). Dictionary safety in signed-manifest mode is a specification requirement with no analysis (the manifest is unimplemented, as Table 3 says). *Action:* one clause noting that manifest-mode dictionary safety is specified but not analyzed here.

### R5-4 (minor) — Jain-index scale for two flows
For n = 2 flows Jain's index ranges from 0.5 (maximally unequal) to 1.0, so the measured encoded-rate value of 0.722 sits mid-scale, not near the floor of a [0,1] range as a casual reader might assume. *Action:* add "(for two flows the index ranges 0.5–1.0)" where the values are reported.

### R5-5 (housekeeping) — Stale auxiliary documents in the package
`paper/evidence_tables.md` still says "Version 2.4 Evidence Tables," and the `docs/evidence_hierarchy_*` series stops at v2.9 while internal notes continue to v3.x. A reviewer opening the artifact will notice. *Action:* refresh the evidence-tables header/content or remove it from the submission package; add or consolidate an up-to-date evidence hierarchy.

## 4. Assessment of the v3.2 additions

- **§7.5 (trace):** the strongest single improvement across all five rounds. Mixed results (12.4x/11.2x on stable patch releases vs 1.1–1.9x where gzip wins) reported without spin are exactly what credible external evidence looks like. With the R5-1 disclosure it is solid.
- **§10 (measured fairness):** replacing the 2-round smoke test with 12 measured rounds and reporting the *less favorable* encoded-rate index (0.722, down from the earlier 0.919 snapshot) is scientifically honest and materially strengthens trust. The kernel-netem limitation is stated with its concrete cause.
- **§4.5 (security):** an appropriate level of formality for an applied venue: a real adversary model and a reduction argument grounded in the actual construction, with truncation and keying caveats. R5-2/R5-3 are wording-level fixes.

## 5. Disposition

All five findings are paper-side edits totaling perhaps ten sentences plus housekeeping; no new experiments are needed. After they are applied, I see no remaining barrier to submission at the target venue class. The residual future-work items (custom QUIC frames, live exporter keys, kernel-netem study, machine-checked proof, live registry traces) are correctly disclosed and are research directions, not review defects.
