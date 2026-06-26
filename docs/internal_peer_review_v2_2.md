# Internal peer review notes, Version 2.2

The current package addresses the main remaining strong-journal objections identified in the prior review round.

## Improvements

- The manuscript title block is no longer written as release notes.
- aioquic-dependent tests now skip gracefully when aioquic is unavailable.
- The component-cost table no longer reports an alarming encode-only `reconstruction_ok=false`; HMAC encode/decode is measured as a roundtrip check.
- Native aioquic scaling runs cover 96 KiB, 512 KiB, and 1 MiB update sizes.
- A portable bottleneck-emulation analysis applies shared service rates to measured raw-QUIC and ReduLink-over-QUIC stream-payload bytes.
- README and package paths were cleaned to remove stale v1.x/v2.0 references.

## Remaining limitations

- The implementation is still a QUIC stream mapping rather than custom QUIC extension frames.
- The included corpora remain deterministic fixtures; reviewer-supplied external corpora should be run through the manifest runner for final journal submission.
- The bottleneck analysis is portable and unprivileged, but not a kernel tc/netns congestion-control study.
