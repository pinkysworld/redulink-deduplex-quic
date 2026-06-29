# Reference audit

The manuscript contains 22 numbered references and every numbered reference is
cited before the reference list. The automated checker is:

```bash
python3 scripts/check_manuscript_citations.py
```

Reference roles:

- [1]-[4] establish redundancy elimination, enterprise redundancy, SmartRE, and EndRE.
- [5] establishes the low-bandwidth file-system / file-delta context.
- [6]-[10] establish QUIC transport, QUIC TLS, loss recovery, applicability, and manageability.
- [11]-[13] establish content-defined chunking and chunking-attack context.
- [14] provides Ethernet line-rate context.
- [15] cites the ReduLink artifact.
- [16]-[17] establish deduplication privacy and server-aided deduplication context.
- [18] cites the aioquic implementation used for the native QUIC stream-mapping artifact.
- [19]-[22] establish the HTTP delta / shared-dictionary lineage (RFC 3229 delta
  encoding, VCDIFF/RFC 3284, SDCH, and RFC 9842 Compression Dictionary Transport)
  against which ReduLink is differentiated.

[11] is cited as W. Xia et al. (FastCDC, IEEE TPDS 2020); [19]-[22] are the
nearest receiver-side-reuse prior work and are contrasted in Section 3.3.
