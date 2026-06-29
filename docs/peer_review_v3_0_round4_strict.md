# Strict peer review (round 4) — ReduLink v3.0

**Version reviewed:** v3.0
**Reviewer posture:** strict / skeptical referee at a competitive applied-systems venue. Earlier rounds fixed correctness, structure, references, and presentation; this round deliberately pressures the *substance* of the evidence and the novelty.

---

## 1. Recommendation

**Major revision.** The manuscript is now clean, internally consistent, reproducible, and honest about scope — that is real and uncommon. But under a strict lens the central empirical case is weaker than the polish suggests, for three reasons that are not presentation issues: the headline positive results come from author-constructed fixtures whose composition is undisclosed; the "fairness" evidence is an analytic formula rather than a measurement; and the transport evaluation is toy-scale. None of these is a correctness error, and several are partially acknowledged, but a demanding referee will not accept the positive claims at face value until they are reframed and, ideally, supported by at least one independent measurement.

## 2. Major concerns

### S1 — The strongest positive numbers are mechanically determined by undisclosed, near-total warm overlap
The headline multipliers come from deterministic fixtures whose unchanged fraction the author chose, and that fraction is not reported in the paper. From the committed data:

| Fixture | Input bytes | Changed bytes | Unchanged | Reported multiplier |
|---|---|---|---|---|
| repository-snapshot | 501,760 | **210** | **~100%** | 24.73x |
| disk-snapshot | 1,048,576 | 28,487 | 97.3% | 28.49x |
| oci-layer | 296,960 | 10,256 | 96.5% | 11.05x |

The effective multiplier is essentially `1 / (1 - unchanged_fraction)`, so "24.73x" on the repository fixture is close to a restatement that only 210 bytes changed — an almost-empty transfer. A skeptical reader cannot tell whether 96–100% overlap is representative of any real workload, because the paper never states the composition. Worse, the *only* genuinely external inputs (the public source releases) are **negative** for ReduLink, and the positive object-aligned experiment is a re-framing of those same bytes. So there is currently **no independent positive measurement** — the positive case rests on constructed fixtures and a re-framing.
*Needed:* (a) disclose each fixture's warm/changed composition in the paper and state explicitly that the multiplier tracks the chosen overlap; (b) reframe the fixtures as illustrative upper-bound shapes, not evidence of real-world gain; (c) ideally add at least one independent positive trace (e.g., real successive OCI image layers or container registry pulls), which is the single most valuable thing that would lift this paper.

### S2 — The "fairness" bottleneck table is arithmetic, not an experiment
Table 18's completion times reproduce, to within a small constant, `encoded_bytes x 8 / rate + 2 x RTT`. The reconstructed-goodput "advantage" is therefore arithmetically guaranteed the moment ReduLink sends fewer encoded bytes; it is not evidence of fair coexistence under a real congestion controller. The competing-flow result is a 2-round localhost smoke test, and the wire-byte accounting is a 16-round counting exercise. The text caveats these as "emulation" and "smoke test," which is good, but a strict referee reads a six-row table of "Mbps" as a measurement.
*Needed:* relabel Table 18 as an analytic model (e.g., "Analytic fluid-model completion times"), state the closed-form explicitly, and avoid the word "goodput" for a computed quantity; defer any fairness *claim* to a real tc/netem or Mininet study with a standard congestion controller and competing real flows.

### S3 — The security evaluation is self-consistent functional testing, not adversarial or formal analysis
The "authenticated" contribution is validated by the artifact checking that its own HMAC rejects a tampered tag and a replayed nonce. That is necessary but nearly tautological: it demonstrates the code does what it was written to do, not that the design resists a defined adversary. There is no formal model, no reduction, no replay-window analysis, and the production keying (QUIC TLS exporter) and replay policy are unimplemented. For an applied-systems venue this can be acceptable, but the paper should stop implying the security property is *evaluated* and instead state that it is *specified and functionally smoke-tested*.
*Needed:* a sentence in the threat model and limitations explicitly bounding the security evidence to artifact-level functional tests; for a security-leaning venue, a defined adversary model and at least an informal argument.

## 3. Moderate concerns

### S4 — Transport evidence is toy-scale
Every native-QUIC experiment uses <= 1 MiB over localhost on a single connection; most use ~96 KB. Multipliers are deterministic so they will not change with size, but completion times, miss dynamics, dictionary eviction, flow-control interaction, and fairness emphatically will. The transport claims should be explicitly scoped to "small, single-connection, loopback" and the scale stated numerically.

### S5 — Novelty framing is vulnerable
After the (welcome) addition of the HTTP shared-dictionary related work, a referee can reasonably recast the contribution as "Compression Dictionary Transport plus a per-reference HMAC plus a MISS/FULL repair handshake." That is a legitimate increment, but the paper should preempt the "is this just CDT with authentication?" question head-on, ideally by articulating a concrete threat or failure scenario that CDT cannot handle but ReduLink can (e.g., a partially-trusted or shared origin dictionary where per-reference context binding matters), rather than asserting the difference in the abstract.

## 4. Minor

- The abstract's "recovers redundancy savings without breaking encryption" slightly overstates; ReduLink recovers savings *for warm receivers only*, which the abstract should say in the first sentence.
- Table 20 marks CDT as "fail-closed repair: No"; CDT does fall back to standard compression, so "No (codec fallback, not fail-closed)" is fairer wording.
- "Effective application multiplier 10.72x" in Section 10 comes from a different small experiment than the headline numbers and may read as inconsistent; tie it to its specific fixture.
- n = 3 repeated trials and 2 competing-flow rounds are too few to report standard deviations as if meaningful.

## 5. What is genuinely strong (and should be preserved)
The claim boundary, the reporting of decisively negative results (rsync winning by up to 73x), the reproducibility package, and the accounting discipline (crediting savings only as encoded bytes) are all above the norm. The paper's honesty is its best feature; the fixes above are about making the *evidence* as disciplined as the *framing*.

## 6. Disposition

Paper-side items that can be adapted now without new experiments: S1(a-b) disclosure and reframing, S2 relabeling, S3/S4 caveats, S5 novelty preemption, and all minors. Items that require **new work** and cannot be fixed by editing: an independent positive trace (S1c), a real-network fairness study (S2), and a formal/adversarial security analysis (S3). The latter three are the honest boundary between "well-written" and "strongly evidenced," and at least one independent positive measurement is what I would most want before acceptance.
