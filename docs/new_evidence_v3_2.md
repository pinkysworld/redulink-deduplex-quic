# New evidence added in v3.2 (closing the strict-review gaps)

The strict round-4 review flagged three items that could not be fixed by editing.
v3.2 closes two with real new experiments and one with new analysis; the residual
parts that genuinely require a privileged host or external infrastructure are
stated as future work.

## 1. Independent captured positive trace (Section 7.5, Table 11)
`benchmarks/run_pypi_object_trace.py` downloads the wheels of two consecutive
released versions of six widely used Python packages directly from PyPI (via
`pip download`), records the SHA-256 of every wheel, and measures object reuse
with the same accounting as Section 7.2; a real `redulink_model` round trip
confirms byte-exact reconstruction. Results (`results/pypi_object_trace.csv`)
are honestly mixed: rich 13.7.0->13.7.1 (76/82 files unchanged) = 12.41x and
click 8.1.6->8.1.7 = 11.17x, while feature/minor upgrades (jinja2, urllib3,
packaging) fall to 1.1-1.9x where gzip wins. Neither corpus nor overlap was
author-chosen, so this is the strongest external positive evidence.

## 2. Measured competing-flow fairness (Section 10, Table 18)
The 2-round "smoke test" was replaced by a real 12-round concurrent measurement
(`benchmarks/run_quic_competing_flows.py --rounds 12`). Measured Jain indices:
reconstructed-rate 0.923, encoded-rate 0.722 (the lower encoded-rate index
reflects ReduLink's smaller byte volume, not transport unfairness). The bottleneck
table remains explicitly analytic. A kernel tc/netem or Mininet study needs
NET_ADMIN on a privileged host and remains future work (it cannot run in the
unprivileged build environment).

## 3. Formal security analysis (Section 4.5)
A Dolev-Yao adversary model, four precise security goals (reference
unforgeability, context binding/replay resistance, expansion bound, dictionary
safety), and a reduction-style theorem: under HMAC-SHA-256 EUF-CMA and SHA-256
collision-resistance, ReduLink reference substitution is unforgeable and
context-binding. Honest caveats on 128-bit truncation and exporter-vs-test keying
are stated. New references: HMAC [23], HKDF [24], Jain fairness index [25].

## Verification
Citation checker 25/25; tables renumbered to 1-21 contiguous; new
`tests/test_pypi_object_trace.py` validates the committed trace; all numbers
reconcile to results/*.
