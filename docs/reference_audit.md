# Reference audit

The v3.15 manuscript contains 32 numbered references and cites every reference
before the reference list. Verify numbering with:

```bash
python scripts/check_manuscript_citations.py
```

Reference roles:

- [1-3] establish link and network-wide redundancy elimination.
- [4-7] establish the closest endpoint lineage: EndRE, DOT, PACK, and CoRE.
- [8-10] establish rsync, LBFS, and REBL as file, chunk, and collection-level
  delta-transfer comparators.
- [11-13] establish HTTP delta encoding, VCDIFF, and RFC 9842 Compression
  Dictionary Transport.
- [14-18] define QUIC transport, TLS use, recovery, applicability, and
  manageability.
- [19] defines the current TLS 1.3 exporter construction.
- [20-21] define HMAC and HKDF.
- [22] establishes FastCDC as related content-defined chunking work; the paper
  explicitly does not attribute FastCDC behavior to its own exploratory
  rolling-hash chunker.
- [23-24] ground the deduplication side-channel discussion.
- [25-26] define Zstandard and its raw-content-dictionary format.
- [27] identifies the aioquic implementation and version used by the artifact.
- [28] identifies the source and reproducibility package.
- [29] supplies the standard pseudorandom-function analysis cited for the
  deliberately qualified HMAC tag argument.
- [30] documents Tentackle's industrial TRIP-over-QUIC transport, dictionary,
  back-reference, and optional compression design.
- [31] identifies the exact python-zstandard binding version used by the
  artifact.
- [32] defines exporter label and application-context requirements, including
  the unregistered `EXPERIMENTAL` private-use namespace.

The novelty boundary does not attribute endpoint substitution, hash-named
chunks, miss recovery, file delta, HTTP dictionary transport, or carrying an
existing dictionary-aware RPC protocol over QUIC to ReduLink.
Its claim is limited to the implemented bounded QUIC application-stream mapping
and the accompanying evaluation.
