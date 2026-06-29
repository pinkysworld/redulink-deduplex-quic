# Internal peer review notes for v3.1

Version 3.1 adapts the editable outcomes of the strict round-4 review
(`docs/peer_review_v3_0_round4_strict.md`). Items requiring new experiments are
flagged in the text rather than fabricated.

## Adapted (paper-side, no new data)
- S1: Table 6 now discloses each fixture's constructed unchanged fraction
  (96-100% on positive rows; repository fixture changes only 210 of 501,760
  bytes), and Sections 6-7 reframe the fixtures as illustrative workload shapes,
  not real-world gains; the only external inputs (source releases, negative; and
  their object-aligned re-framing, positive) are named as such.
- S2: Table 18 is relabeled as an analytic fluid model (completion ~ encoded x 8
  / rate + 2 x RTT), explicitly computed not measured; the competing-flow result
  is called a two-round localhost smoke test.
- S3: threat model and limitations now state the security evidence is artifact-
  level functional testing, not a formal or adversarial analysis.
- S4: limitations now state the transport scale numerically (<= 1 MiB, single
  localhost connection).
- S5: Section 3.3 preempts the "CDT + HMAC?" question with a concrete shared /
  partially trusted origin-dictionary integrity scenario CDT cannot handle.
- Minors: abstract warm-receiver qualifier; Table 20 CDT cell "not fail-closed";
  10.72x tied to its 48 KiB fixture; n=3 trials framed as stability indicators.

## NOT adapted (require new experiments; flagged in text as future work)
- An independent captured positive trace (S1c).
- A real tc/netem or Mininet fairness study (S2).
- A formal/adversarial security analysis (S3).

## Verification
Citation checker 22/22; Table 6 unchanged fractions reconcile to results/*;
14 pp / ~6.5k words.
