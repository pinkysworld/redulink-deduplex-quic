# Benchmark Summary

- cpython-http-server:cold-intra-artifact: best redulink (cdc) multiplier=0.998, savings=0.000
- cpython-http-server:single-object: best gzip-6 (none) multiplier=3.266, savings=0.694
- cpython-http-server:warm-update-like: best fixed-block-reuse (fixed) multiplier=1.201, savings=0.168
- cpython-pathlib:cold-intra-artifact: best redulink (cdc) multiplier=0.997, savings=0.000
- cpython-pathlib:single-object: best gzip-6 (none) multiplier=4.069, savings=0.754
- cpython-pathlib:warm-update-like: best fixed-block-reuse (fixed) multiplier=1.000, savings=0.000
- ietf-quic-rfc:cold-intra-artifact: best redulink (cdc) multiplier=0.998, savings=0.000
- ietf-quic-rfc:single-object: best gzip-6 (none) multiplier=3.221, savings=0.690
- ietf-quic-rfc:warm-update-like: best fixed-block-reuse (fixed) multiplier=1.000, savings=0.000
- linux-kernel-parameters:cold-intra-artifact: best redulink (cdc) multiplier=0.998, savings=0.000
- linux-kernel-parameters:single-object: best gzip-6 (none) multiplier=2.915, savings=0.657
- linux-kernel-parameters:warm-update-like: best fixed-block-reuse (fixed) multiplier=1.031, savings=0.030
- nginx-changes:cold-intra-artifact: best redulink (cdc) multiplier=0.998, savings=0.000
- nginx-changes:single-object: best gzip-6 (none) multiplier=5.400, savings=0.815
- nginx-changes:warm-update-like: best fixed-block-reuse (fixed) multiplier=72.956, savings=0.986
- redis-readme:cold-intra-artifact: best redulink (fixed) multiplier=0.997, savings=0.000
- redis-readme:single-object: best gzip-6 (none) multiplier=2.628, savings=0.620
- redis-readme:warm-update-like: best redulink (cdc) multiplier=1.565, savings=0.361

Rows marked comparable=False remain in the CSV but are excluded from plots and best-method summary selection.
