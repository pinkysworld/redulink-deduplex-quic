# Internal peer review notes for v2.7

## Summary

Version 2.7 strengthens the v2.6 manuscript by expanding the deployment model, evidence hierarchy, evaluation methodology, security/threat table, and practical motivation relative to compression and rsync. The paper is now framed more explicitly as authenticated, scoped, QUIC-compatible reference substitution rather than a superior byte-matching algorithm.

## Remaining honest limits

- Native aioquic stream mapping is implemented, but custom QUIC extension frames and transport-parameter negotiation remain future work.
- Public object-aligned release workloads use real release bytes but are transfer-model evidence, not captured production registry traces.
- Fairness evidence remains conservative and does not replace a full live network-emulator congestion-control study.

## Submission posture

The paper is suitable for a strong applied networking/systems journal after final venue-specific formatting. For a top-tier systems venue, custom QUIC integration or live packet-level fairness evidence would still be expected.
