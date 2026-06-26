# Reference and Citation Audit, Version 2.3

Scope: `paper/submission/ReduLink_journal_ready_v2_3.docx`, reference list, and visible in-text numeric citations.

Automated check:

```bash
python3 scripts/check_manuscript_citations.py
```

Expected result:

```text
citation check OK: 18 references, 18 cited in manuscript body
```

Manual audit notes:

- References [1]-[5] cover classical redundancy elimination, SmartRE, enterprise redundancy findings, EndRE, and LBFS.
- References [6]-[10] cover QUIC transport, TLS for QUIC, loss/congestion recovery, applicability, and manageability.
- References [11]-[13] cover content-defined chunking performance, CDC behavior, and chunking attacks.
- Reference [14] supports Ethernet/physical line-rate context.
- Reference [15] is the artifact/repository reference.
- References [16]-[17] cover deduplication side channels and server-aided encryption for deduplicated storage.
- Reference [18] documents aioquic as a Python QUIC/HTTP/3 implementation and supports the native aioquic stream-mapping experiment.

No uncited references or dangling citation numbers were found by the checker.
