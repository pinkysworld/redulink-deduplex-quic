# Artifact evaluation checklist

- Repository: `https://github.com/pinkysworld/redulink-deduplex-quic`
- Manuscript PDF: `paper/submission/ReduLink_submission_v3_17.pdf`
- Manuscript DOCX: `paper/submission/ReduLink_submission_v3_17.docx`
- Highlights: `paper/submission/HIGHLIGHTS.txt`
- Review mapping: `REVIEWER_RESPONSE_v3_17.md`
- Evidence source revision: `SOURCE_COMMIT.txt`
- Manuscript hashes: `MANUSCRIPT_SHA256.txt`

## Integrity checks

```bash
python scripts/check_text_line_endings.py
python scripts/check_manuscript_citations.py
python scripts/check_manuscript_hashes.py
python scripts/run_full_validation.py
```

Expected properties:

- Every stateful method verifies exact bytes or an exact ordered object/tree
  manifest.
- The complete IBM trace result verifies the public archive SHA-1, preserves
  production/nonproduction classification, and labels LRU hits as an upper
  bound rather than client-cache truth.
- Registry-layer rows pin index and platform-manifest digests, verify every
  compressed blob, and remove whole-layer CAS hits before chunk analysis.
- Linux path rows contain 16 conditions, 20 paired rounds, Reno, one-clock
  client completion and FIRST_BYTE timing, exact reconstruction, and root-qdisc
  counters.
- Multistream rows use one live exporter and actual stream IDs 0, 4, 8, 12,
  and 16. Fairness rows synchronize first application writes and calibrate
  encoded work in the mixed case.
- CPU scaling covers 64 KiB through 32 MiB, and the replay window remains
  bounded at 4,096 entries through 100,000 sequential nonces.
- Native QUIC rows separate forward protocol bytes, reverse repair/control
  bytes, and excluded diagnostic STATS bytes.
- Binary CID, frame, connection-context, exporter-context, and key-schedule
  vectors have an independently encoded test oracle.
- Native client and server use matching live TLS 1.3 exporter outputs; the
  private bridge fails closed outside pinned aioquic 1.3.0.
- `results/deployment_envelope.*` verifies every miss row against
  `B(m)=15914+1149m` and treats warm-state residency as a separate gate.
- Raw-tree profile rows reconstruct from decoded binary messages.
- zstd headline rows pin window_log 21 and include window_log 24 sensitivity.
- The native code reads the actual aioquic application stream identifier.
- HELLO carries a QUIC/TLS-protected reconstruction declaration that is checked
  against server-configured expectations; the receiver also enforces per-frame,
  declared-length, and global reconstruction bounds.
- HELLO's exact frame count is bounded so the single MISSING batch fits under
  the binary message-size limit.
- Successful references refresh true-LRU state.
- Repair is batched after `END_ROUND`; no `DICT_ACK` is implemented or claimed.
- The 13-byte FIRST_BYTE acknowledgement and STATS diagnostics are reported but
  excluded from ReduLink protocol-byte multipliers.
- Public corpus versions and SHA-256 digests are retained in manifests or
  result files.

## Interpretation checks

- QUIC/TLS, not the record HMAC, is the on-path security boundary.
- Stream-payload multipliers remain distinct from packet metrics. The Linux
  study reports root-qdisc packet and byte deltas separately.
- Single-host results support only their controlled path, stream, fairness, and
  Python implementation conditions; they are not multi-host Internet claims.
- Public releases and wheels are reproducible workloads, not production-trace
  samples.
- The author-constructed Redis layer fixture is not represented as a captured
  registry trace.
- Historical asymmetric-clock timing and userspace path-emulation outputs are
  excluded from manuscript conclusions.
- The default evidence-checker mode rebuilds figures and the normalized DOCX in
  temporary paths and checks fixed-PDF provenance and headline claims. CI separately regenerates deterministic tables and invokes
  the checker's `--generated-dir` comparison mode.
