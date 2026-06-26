# Benchmark Summary

- independent-compressed-negative:cold-intra-artifact: best redulink (cdc) multiplier=0.997, savings=0.000
- independent-compressed-negative:single-object: best raw (none) multiplier=1.000, savings=0.000
- independent-compressed-negative:warm-update-like: best fixed-block-reuse (fixed) multiplier=1.000, savings=0.000
- scripted-disk-snapshot:cold-intra-artifact: best redulink (fixed) multiplier=1.051, savings=0.049
- scripted-disk-snapshot:single-object: best zstd-3 (none) multiplier=1.062, savings=0.058
- scripted-disk-snapshot:warm-update-like: best fixed-block-reuse (fixed) multiplier=31.973, savings=0.969
- scripted-oci-layer:cold-intra-artifact: best redulink (cdc) multiplier=0.996, savings=0.000
- scripted-oci-layer:single-object: best zstd-3 (none) multiplier=1.496, savings=0.332
- scripted-oci-layer:warm-update-like: best redulink (fixed) multiplier=11.054, savings=0.910
- scripted-package-metadata:cold-intra-artifact: best redulink (cdc) multiplier=0.999, savings=0.000
- scripted-package-metadata:single-object: best gzip-6 (none) multiplier=14.309, savings=0.930
- scripted-package-metadata:warm-update-like: best fixed-block-reuse (fixed) multiplier=9.880, savings=0.899
- scripted-repository-snapshot:cold-intra-artifact: best redulink (fixed) multiplier=1.002, savings=0.002
- scripted-repository-snapshot:single-object: best zstd-3 (none) multiplier=10.372, savings=0.904
- scripted-repository-snapshot:warm-update-like: best redulink (fixed) multiplier=24.732, savings=0.960
- scripted-structured-logs:cold-intra-artifact: best redulink (cdc) multiplier=0.999, savings=0.000
- scripted-structured-logs:single-object: best zstd-3 (none) multiplier=18.012, savings=0.944
- scripted-structured-logs:warm-update-like: best fixed-block-reuse (fixed) multiplier=14.887, savings=0.933

Rows marked comparable=False remain in the CSV but are excluded from plots and best-method summary selection.
