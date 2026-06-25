# Benchmark Summary

- cpython-http-server:cold-intra-artifact: best redulink (cdc) multiplier=0.998, savings=0.000
- cpython-http-server:single-object: best gzip-6 (none) multiplier=3.259, savings=0.693
- cpython-http-server:warm-update-like: best redulink (cdc) multiplier=11.437, savings=0.913
- ietf-quic-rfc:cold-intra-artifact: best redulink (cdc) multiplier=0.998, savings=0.000
- ietf-quic-rfc:single-object: best gzip-6 (none) multiplier=3.217, savings=0.689
- ietf-quic-rfc:warm-update-like: best rsync-block-reuse (fixed) multiplier=1.000, savings=0.000
- linux-kernel-parameters:cold-intra-artifact: best redulink (cdc) multiplier=0.997, savings=0.000
- linux-kernel-parameters:single-object: best gzip-6 (none) multiplier=2.914, savings=0.657
- linux-kernel-parameters:warm-update-like: best rsync-block-reuse (fixed) multiplier=1.031, savings=0.030

Rows marked comparable=False remain in the CSV but are excluded from plots and best-method summary selection.
