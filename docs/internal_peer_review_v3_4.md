# Internal peer review notes for v3.4

Version 3.4 adapts the round-6 internal review (`docs/peer_review_v3_3_round6.md`)
and the second external review of v3.3.

## Headline change (new measured evidence)
`benchmarks/run_quic_emulated_path.py` runs a raw and a ReduLink aioquic flow
concurrently through a shared userspace token-bucket + delay path (5/20 Mbps x
20/80 ms RTT, 3 rounds each, instrumented queueing delay). The measured result
contradicts the analytic fluid model: despite 3.19x fewer encoded bytes,
ReduLink completes ~74% slower at 5 Mbps/20 ms (1275 vs 731 ms; mean queue
delay ~24 ms), and within 3-10% at 20 Mbps (queue ~1 ms). Section 10 now
presents the measured table (Table 19) as primary and retains the fluid model
only as an explicitly optimistic best-case bound. The claim boundary is
sharpened: byte-cost reduction at equal fairness, not single-transfer latency.

## Other changes
- Byline: personal domain removed (author instruction).
- Harness: proxy and run helpers gained an optional additive `shaper` parameter
  (defaults unchanged; full suite 47 tests passes).
- Docstring honesty: run_quic_competing_flows.py no longer claims shaping it
  does not perform.
- README rewritten: wrapped lines, smoke-first validation, tag reference, new
  experiments listed, limitations updated.
- New CI-safe test `tests/test_quic_emulated_path.py` validates committed
  results.

## Deferred to the user (web-only)
GitHub Release from the tag, repository About-description fix, landing-page
cache check.
