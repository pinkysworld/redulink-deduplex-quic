# Reviewer Response Matrix - v3.14 Candidate

This matrix maps the peer-review findings for v3.13 to the reviewer-adapted
v3.14 candidate. “Resolved” means the code, evidence, and manuscript now agree.
“Bounded” means the invalid claim was removed and the corrected experiment is
provided, but a new external/kernel execution is still required.

| Finding | Adaptation | Primary evidence | Status |
|---|---|---|---|
| Reused native authentication key/context and disabled certificate verification | Native runs use fresh private exporter-surrogate input and random connection context; the client verifies the ephemeral server certificate against a local trust anchor. Client-certificate authentication and live exporter access remain explicitly out of scope. | `prototypes/redulink_aioquic_experiment.py`, `benchmarks/run_quic_flow_comparison.py`, `tests/test_aioquic_experiment.py` | Resolved |
| Receiver accepted the frame's own offset and trusted external sequence ordering | HELLO fields, initial sequence, independently accumulated reconstructed offset, repair metadata, pending repairs, and exact FINISH sequence are checked before reconstruction. | `QuicReduLinkServer.accept_hello`, `QuicReduLinkServer.accept_frame`, native wrong-offset/corrupt-dictionary tests | Resolved |
| Wire decoder accepted unbounded, truncated, or trailing data | Length prefixes are bounded at 16 MiB; HELLO, control, FRAME, and MISSING messages require exact lengths; invalid flags/kinds and trailing bytes fail closed. | `src/redulink_wire.py`, `tests/test_redulink_wire.py` | Resolved |
| Clean-clone smoke/full validation failed because ignored target corpora were absent | Both validation entry points generate deterministic target corpora before checking their manifest and hashes. Validation was repeated from a patched fresh clone with no initial `data/target_corpora`. | `scripts/run_smoke_validation.py`, `scripts/run_full_validation.py`, `benchmarks/check_generated_artifacts.py` | Resolved |
| v3.12/v3.13 metadata and artifact paths drifted | Project metadata, citation metadata, active builder, manuscript paths, reviewer docs, inventory, source-status files, and hashes now identify v3.14. The status files distinguish the candidate review branch from an immutable public tag/release. | `pyproject.toml`, `CITATION.cff`, `SOURCE_COMMIT.txt`, `SOURCE_GIT_STATUS.txt`, `MANUSCRIPT_SHA256.txt`, `INVENTORY.txt` | Resolved |
| CDT comparison understated RFC 9842 and overstated inner-HMAC network security | The manuscript now describes SHA-256 dictionary identity, HTTPS same-origin/availability policy, and response discard on decode failure. QUIC AEAD is the on-path security boundary; ReduLink tags are positioned as post-TLS reference/dictionary-state binding. `zstd --patch-from` is labeled whole-stream dictionary delta, not CDT. | Manuscript Sections 3.3, 4.4-4.5, 7.6, 12-13; `README.md` | Resolved |
| Truncated-HMAC theorem relied on EUF-CMA alone | The theorem now explicitly assumes HMAC PRF/random-function behavior for 128-bit truncation, adds tag-guess and identifier-birthday terms, and keeps SHA-256 collision resistance separate. | Manuscript Section 4.5; `docs/evidence_hierarchy.md` | Resolved |
| Object workload declared reconstruction successful without decoding names/boundaries; PyPI used an unrelated flat stream | The runner builds and decodes ordered named-object records, preserves empty objects, checks exact names/lengths/contents, authenticates secure object headers, and shares warm state across objects. PyPI uses this same decoder and no longer reports the flat-stream proxy. | `benchmarks/run_external_object_workload_suite.py`, `benchmarks/run_pypi_version_pair_object_study.py`, object tests and regenerated results | Resolved |
| Transport comparisons mixed concurrent and isolated designs; ratio summaries and Jain interpretation were inconsistent | Userspace completion summaries use mean within-round ratios and retain ratio-of-means separately. Unshaped Jain values are per-round rate-balance diagnostics, not fairness. Bootstrap intervals are labeled within-run localhost variability only. | `benchmarks/run_quic_emulated_path.py`, `benchmarks/run_quic_competing_flows.py`, `benchmarks/summarize_quic_statistical_evidence.py`, Tables 19-22 | Resolved |
| Linux netem result was concurrent, lacked provenance, and was presented as isolated/load-bearing | The legacy result is explicitly marked `concurrent_legacy` with unavailable provenance fields and is retained only as exploratory contention evidence. The corrected runner defaults to isolated, order-alternated pairs and records command, platform, Python, aioquic, tc, commit, and qdisc snapshots. | `benchmarks/run_linux_netem_quic_path.py`, `results/linux_netem_quic_path.json`, manuscript Table 23 | Bounded - corrected Linux rerun pending |
| zstd and system-tool environment was not pinned; rsync provenance was absent | zstd 1.5.7 is source/checksum pinned; its exact command/version and fixed-plus-scope framing formula are recorded. Docker installs rsync, iproute2/tc, and util-linux/taskset. CI uses `requirements-lock.txt`. rsync rows now record executable and version. | `Dockerfile`, `.github/workflows/tests.yml`, framing and rsync runners/results | Resolved |
| Binary framing was described as universally 108 bytes | The artifact and manuscript state `79 + UTF-8 scope length`: 95 bytes for the 16-byte native scope and 108 bytes for the 29-byte repricing scope. | `src/redulink_wire.py`, `benchmarks/run_framing_dictionary_baseline.py`, manuscript Sections 4.1 and 7.6 | Resolved |
| Tables split badly or used unreadably small type | Table headers repeat, rows do not split, captions stay with tables, page breaks keep Tables 10 and 26 together, and the smallest security/positioning tables use larger type. Every final PDF page was rendered and visually inspected. | `scripts/build_manuscript_v3_14.py`, final 18-page PDF | Resolved |
| SDCH reference year was wrong | Reference [21] now identifies `draft-lee-sdch-spec-00` as a 2016 Internet-Draft. | Manuscript reference [21], `docs/reference_audit.md` | Resolved |

## Validation record

- Pinned environment: `requirements-lock.txt`, aioquic 1.3.0.
- Local smoke and full validation: passed.
- Fresh-clone candidate smoke and full validation with initially absent generated
  target corpora: passed.
- Isolated unittest modules: 33; all passed.
- Manuscript citations: 26 references, 26 cited.
- PDF/DOCX hashes: verified by `MANUSCRIPT_SHA256.txt`.
- PDF layout: all 18 rendered pages visually inspected.

The candidate branch commit/push is version-control delivery only. No immutable
tag, GitHub Release, or corrected Linux kernel sweep is implied by this matrix.
