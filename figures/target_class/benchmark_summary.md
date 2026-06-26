# Benchmark Summary

- compressed-related-warm-generated:cold-intra-artifact: best redulink (cdc) multiplier=0.997, savings=0.000
- compressed-related-warm-generated:single-object: best zstd-3 (none) multiplier=2.192, savings=0.544
- compressed-related-warm-generated:warm-update-like: best fixed-block-reuse (fixed) multiplier=12.417, savings=0.919
- container-layer-generated:cold-intra-artifact: best redulink (cdc) multiplier=0.999, savings=0.000
- container-layer-generated:single-object: best zstd-3 (none) multiplier=4.087, savings=0.755
- container-layer-generated:warm-update-like: best fixed-block-reuse (fixed) multiplier=1.799, savings=0.444
- git-packlike-generated:cold-intra-artifact: best redulink (fixed) multiplier=0.997, savings=0.000
- git-packlike-generated:single-object: best zstd-3 (none) multiplier=18.080, savings=0.945
- git-packlike-generated:warm-update-like: best fixed-block-reuse (fixed) multiplier=1.269, savings=0.212
- independent-compressed-negative-generated:cold-intra-artifact: best redulink (cdc) multiplier=0.998, savings=0.000
- independent-compressed-negative-generated:single-object: best raw (none) multiplier=1.000, savings=0.000
- independent-compressed-negative-generated:warm-update-like: best fixed-block-reuse (fixed) multiplier=1.000, savings=0.000
- random-negative-generated:cold-intra-artifact: best redulink (cdc) multiplier=0.998, savings=0.000
- random-negative-generated:single-object: best raw (none) multiplier=1.000, savings=0.000
- random-negative-generated:warm-update-like: best fixed-block-reuse (fixed) multiplier=1.000, savings=0.000
- software-update-generated:cold-intra-artifact: best redulink (cdc) multiplier=0.999, savings=0.000
- software-update-generated:single-object: best zstd-3 (none) multiplier=11.958, savings=0.916
- software-update-generated:warm-update-like: best fixed-block-reuse (fixed) multiplier=1.000, savings=0.000
- structured-logs-generated:cold-intra-artifact: best redulink (cdc) multiplier=0.999, savings=0.000
- structured-logs-generated:single-object: best gzip-6 (none) multiplier=12.397, savings=0.919
- structured-logs-generated:warm-update-like: best fixed-block-reuse (fixed) multiplier=1.070, savings=0.065
- vm-backup-generated:cold-intra-artifact: best redulink (cdc) multiplier=0.999, savings=0.000
- vm-backup-generated:single-object: best zstd-3 (none) multiplier=9.949, savings=0.899
- vm-backup-generated:warm-update-like: best fixed-block-reuse (fixed) multiplier=21.560, savings=0.954

Rows marked comparable=False remain in the CSV but are excluded from plots and best-method summary selection.
