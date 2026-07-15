# Artifact evaluation checklist

- Repository: `https://github.com/pinkysworld/redulink-deduplex-quic`
- Manuscript PDF: `paper/submission/ReduLink_journal_ready_v3_15.pdf`
- Manuscript DOCX: `paper/submission/ReduLink_journal_ready_v3_15.docx`
- Journal highlights: `paper/submission/HIGHLIGHTS.txt`
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
- Native QUIC rows separate forward protocol bytes, reverse repair/control
  bytes, and excluded diagnostic STATS bytes.
- Binary CID, frame, connection-context, exporter-context, and key-schedule
  vectors have an independently encoded test oracle.
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
- Public corpus versions and SHA-256 digests are retained in manifests or
  result files.

## Interpretation checks

- QUIC/TLS, not the record HMAC, is the on-path security boundary.
- Stream-payload multipliers are not packet, IP, UDP, or link-layer metrics.
- Single-host QUIC runs support byte and state-machine claims only.
- Public releases and wheels are reproducible workloads, not production-trace
  samples.
- The author-constructed Redis layer fixture is not represented as a captured
  registry trace.
- Historical timing and path-emulation outputs are excluded from manuscript
  conclusions.
- The default evidence-checker mode rebuilds figures and the normalized DOCX in
  temporary paths and checks fixed-PDF provenance and headline claims. CI separately regenerates deterministic tables and invokes
  the checker's `--generated-dir` comparison mode.
