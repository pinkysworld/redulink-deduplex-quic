# Internal peer review (round 6) — ReduLink v3.3, adapted into v3.4

**Version reviewed:** v3.3 | **Outcome version:** v3.4
**Posture:** internal review calibrated to the top-journal bar, run alongside triage of a second external review of v3.3. The goal was to find what could still be *strengthened with real work* rather than wording.

---

## 1. Headline: a new measured experiment that overturns one of the paper's own tables

The most consequential outcome of this round is not an edit but an experiment. Kernel tc/netem remains unavailable in the build environment (NET_ADMIN denied), but nothing prevented a **userspace path emulator**: a shared token-bucket serializer plus one-way propagation delay wrapped around the existing aioquic proxies, so a raw QUIC flow and a ReduLink flow genuinely compete for one emulated bottleneck (5/20 Mbps x 20/80 ms RTT, 3 rounds each; `benchmarks/run_quic_emulated_path.py`).

**The measured result contradicts the paper's analytic fluid model (v3.3 Table 19).** Despite transmitting 3.19x fewer encoded bytes, ReduLink did *not* complete faster; at 5 Mbps / 20 ms it completed ~74% slower than the competing raw flow (1275 ms vs 731 ms). The instrumented shaper shows why: at 5 Mbps the shared queue adds ~24 ms mean (72 ms max) delay behind the raw flow's larger byte volume, and ReduLink's MISS/repair exchange crosses that inflated path more times than a one-way bulk stream; at 20 Mbps (measured queueing ~1 ms) the flows finish within 3–10% of each other. Reconstruction stayed byte-exact everywhere and encoded-rate Jain indices were 0.67–0.78.

**Disposition (adapted):** the measured table becomes the primary bottleneck evidence in Section 10; the fluid model is retained only as an explicitly optimistic upper bound (it ignores queueing and application round trips). The claim boundary is sharpened accordingly: *ReduLink's measured benefit on constrained shared paths is byte-cost reduction at equal fairness, not single-transfer latency; completion-time benefits require miss-free warm state or pipelined bulk transfers.* Publishing a self-measured negative like this is precisely what distinguishes a top-journal submission from an advocacy paper.

## 2. Other findings (adapted)

- **I6-2 — Byline.** Removed the personal domain from the author line per author instruction; venues expect institution + ORCID.
- **I6-3 — Artifact docstring honesty.** `run_quic_competing_flows.py` claimed flows share a "token-bucket-like shaped link," but no shaping existed — the rate was metadata only. Docstring corrected; actual shaping now exists in the new benchmark. (Found only by reading the code against its own comments.)
- **I6-4 — Harness extension kept additive.** The proxy/`run_*` helpers gained an optional `shaper` parameter with unchanged defaults; the full suite (47 tests) passes, so all previously committed results remain valid.
- **I6-5 — Evidence-table row.** The in-paper evidence hierarchy gains a "measured path emulation" row (supports shared-bottleneck completion + queueing behavior; does not prove kernel-netem or Internet-path fairness).

## 3. External review triage (second external report, on v3.3)

Accepted and applied: README polish (one over-long line fixed; smoke-validation-first framing; tag referenced) and keeping fairness/trace limitations conservative. Already satisfied by v3.3: repo/paper synchronization, hash match, tag existence — the reviewer verified these and scored artifact sync 8/10. Not actionable from this environment (user actions on github.com): creating a Release from `v3.3-journal-submission` (now supersede with the v3.4 tag), fixing the repository About description ("effective bandwidth expansion" must go), and confirming the landing page isn't serving a cached README. Judged venue-dependent and deferred: moving dense tables to supplementary material.

## 4. Top-journal readiness assessment

With the measured path-emulation experiment, the fairness/transport evidence moves from "accounting plausibility" to *measured competing-flow behavior with a mechanistic explanation* — the single item both external reviews scored lowest. What still separates this from a confident top-tier submission is unchanged and now explicitly quantified in the paper: custom QUIC extension frames with exporter-derived keys, kernel-level or real-path emulation (netem/Mininet/testbed), captured production registry/CDN traces, and a machine-checked proof. Those require privileged infrastructure or external data access. For a strong applied networking/systems journal, the package is submission-ready after this revision; for a top-tier venue it is an honest "major revision away," with the revision path unambiguous.
