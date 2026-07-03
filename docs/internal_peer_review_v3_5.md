# Internal peer review notes for v3.5

Version 3.5 adapts the final external review of v3.4 (all five cleanup items).

## New evidence (reviewer item 4: larger QUIC run)
The scaling experiment now reaches 16 MiB (16,384 x 1 KiB blocks) and exposes a
finding smaller runs cannot: with the default 8,192-chunk dictionary budget the
16,384-chunk warm set overflows the LRU, sequential FULL admissions cascade-
evict the warm entries, and ReduLink degrades to a FULL-only stream (0.92x,
byte-exact -> fails safe, not wrong). Raising the budget to 24,576 chunks
restores 3.96x and roughly halves completion time (592 vs 1,305 ms). The
harness gained an additive max_dict_chunks knob (client encode, sender and
server dictionaries) and the scaling benchmark a --budgets argument; the exact
reproduction command is:
python3 benchmarks/run_aioquic_scaling_experiment.py \
  --blocks 96 512 1024 4096 16384 16384 --budgets 8192 8192 8192 8192 8192 24576

## Other adapted items
- Item 2: reference [15] now cites the exact tagged release
  (v3.5-journal-submission) with its release URL.
- Item 3: the reproducibility section states that each release ships the final
  PDF/DOCX as assets with hashes pinned in MANUSCRIPT_SHA256.txt.
- Item 5: limitations kept conservative; the scale limitation updated to the
  new measured 16 MiB bound.
- Item 1 (About description): verified already fixed on GitHub
  ("Authenticated reference substitution for encrypted QUIC streams (ReduLink).").

## Verification
Citation checker 25/25; tables 1-22 in order; Table 15 reconciles to
results/aioquic_scaling_experiment.csv; full suite passes.
