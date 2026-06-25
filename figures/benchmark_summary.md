# Benchmark Summary

- logs:cold-intra-artifact: best redulink (cdc) multiplier=0.999, savings=0.000
- logs:single-object: best zstd-3 (none) multiplier=38.746, savings=0.974
- logs:warm-update-like: best fixed-block-reuse (fixed) multiplier=72.694, savings=0.986
- mixed:cold-intra-artifact: best redulink (cdc) multiplier=0.999, savings=0.000
- mixed:single-object: best zstd-3 (none) multiplier=47.692, savings=0.979
- mixed:warm-update-like: best zstd-then-redulink (cdc) multiplier=5.821, savings=0.828
- updates:cold-intra-artifact: best redulink (cdc) multiplier=0.999, savings=0.000
- updates:single-object: best zstd-3 (none) multiplier=38.647, savings=0.974
- updates:warm-update-like: best fixed-block-reuse (fixed) multiplier=63.300, savings=0.984

Rows marked comparable=False remain in the CSV but are excluded from plots and best-method summary selection.
