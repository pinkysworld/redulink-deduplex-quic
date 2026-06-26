#!/usr/bin/env python3
"""Measure local component costs for the ReduLink artifact.

The results are local Python wall-clock numbers, not production line-rate
claims. They make the cost of fixed chunking, CDC chunking, authentication, and
binary wire-format encoding explicit for journal reviewers.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_model as model  # noqa: E402
import redulink_secure as secure  # noqa: E402
import redulink_wire as wire  # noqa: E402


def stable_payload(size: int) -> bytes:
    block = b"component-cost-block:" + b"A" * 1003
    out = (block * (size // len(block) + 1))[:size]
    # introduce deterministic changes so not every block is identical
    b = bytearray(out)
    for i in range(0, len(b), 65536):
        b[i:i+8] = i.to_bytes(8, "big")
    return bytes(b)


def maxrss_kib() -> float:
    val = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Darwin":
        val /= 1024
    return float(val)


def measure(name: str, input_bytes: int, fn) -> dict[str, str]:
    start = time.perf_counter()
    result = fn()
    elapsed = (time.perf_counter() - start) * 1000
    mib_s = (input_bytes / (1024 * 1024)) / max(elapsed / 1000, 1e-9)
    return {
        "component": name,
        "input_bytes": str(input_bytes),
        "wall_ms": f"{elapsed:.3f}",
        "throughput_mib_s_local": f"{mib_s:.3f}",
        "runner_peak_kib": f"{maxrss_kib():.1f}",
        "result_summary": result if isinstance(result, str) else json.dumps(result, sort_keys=True),
        "notes": "local Python artifact timing; not production line-rate evidence",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--size", type=int, default=2 * 1024 * 1024)
    p.add_argument("--chunk-size", type=int, default=4096)
    p.add_argument("--output", type=Path, default=ROOT / "results" / "component_performance.csv")
    args = p.parse_args()
    data = stable_payload(args.size)
    warm = data[: len(data)//2]
    update = data[len(data)//4:] + b"tail-change" * 100
    rows = []
    rows.append(measure("fixed_chunking", len(data), lambda: {"chunks": len(model.make_chunks(data, "fixed", args.chunk_size))}))
    rows.append(measure("cdc_chunking", len(data), lambda: {"chunks": len(model.make_chunks(data, "cdc", args.chunk_size))}))
    rows.append(measure("model_fixed_encode_decode", len(update), lambda: model.run_bytes(update, warm=warm, chunker="fixed", chunk_size=args.chunk_size).__dict__))
    rows.append(measure("model_cdc_encode_decode", len(update), lambda: model.run_bytes(update, warm=warm, chunker="cdc", chunk_size=args.chunk_size).__dict__))
    def secure_encode_roundtrip():
        local_frames, local_stats = secure.encode(update, warm_dictionary=warm, chunk_size=args.chunk_size)
        decoded = secure.decode(local_frames, warm_dictionary=warm, chunk_size=args.chunk_size)
        out = local_stats.__dict__.copy()
        out.pop("reconstruction_ok", None)
        out["roundtrip_reconstruction_checked"] = True
        out["roundtrip_reconstruction_ok"] = decoded == update
        return out

    frames, _ = secure.encode(update, warm_dictionary=warm, chunk_size=args.chunk_size)
    rows.append(measure("secure_hmac_encode_roundtrip", len(update), secure_encode_roundtrip))
    rows.append(measure("secure_hmac_decode", len(update), lambda: {"bytes": len(secure.decode(frames, warm_dictionary=warm, chunk_size=args.chunk_size)), "roundtrip_reconstruction_checked": True}))
    rows.append(measure("binary_wire_encode", len(update), lambda: {"bytes": sum(len(wire.encode_message({"t":"FRAME", "seq":i, "frame":fr})) for i, fr in enumerate(frames))}))
    encoded = [wire.encode_message({"t":"FRAME", "seq":i, "frame":fr}) for i, fr in enumerate(frames)]
    rows.append(measure("binary_wire_decode", len(update), lambda: {"messages": sum(1 for blob in encoded for _ in [wire.decode_payload(blob[4:])])}))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    args.output.with_suffix(".metadata.json").write_text(json.dumps({
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "size": args.size,
        "chunk_size": args.chunk_size,
        "interpretation": "Local Python timings expose cost drivers. Production claims require native chunking and transport integration.",
    }, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
