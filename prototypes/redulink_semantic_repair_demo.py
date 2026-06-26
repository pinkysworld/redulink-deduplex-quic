#!/usr/bin/env python3
"""Deterministic ReduLink semantic repair smoke test.

The prototype models one transport-layer failure case that ordinary packet
retransmission alone cannot solve: a sender believes the receiver dictionary
contains a chunk, sends REF, and the receiver lacks that entry because of
mismatch or eviction. The receiver emits a semantic MISS and the sender repairs
with FULL for the same reconstructed position. This is a representation-layer
experiment, not a QUIC implementation.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_model as redulink


def build_dictionary(data: bytes, *, chunker: str, chunk_size: int, max_chunks: int) -> OrderedDict[str, bytes]:
    dictionary: OrderedDict[str, bytes] = OrderedDict()
    for ch in redulink.make_chunks(data, chunker, chunk_size):
        redulink.touch_lru(dictionary, redulink.cid(ch), ch, max_chunks)
    return dictionary


def thin_dictionary(dictionary: OrderedDict[str, bytes], *, missing_fraction: float, seed: int) -> OrderedDict[str, bytes]:
    rng = random.Random(seed)
    kept: OrderedDict[str, bytes] = OrderedDict()
    for key, value in dictionary.items():
        if rng.random() >= missing_fraction:
            kept[key] = value
    # Ensure at least one miss for deterministic demonstration when possible.
    if dictionary and len(kept) == len(dictionary):
        first = next(iter(kept))
        del kept[first]
    return kept


def frame_wire_bytes(frame: redulink.Frame) -> int:
    if frame.kind == "FULL":
        return redulink.FULL_OVERHEAD + len(frame.payload)
    if frame.kind == "REF":
        return redulink.REF_OVERHEAD
    raise ValueError(f"unknown frame kind: {frame.kind}")


def semantic_repair_run(data: bytes, warm: bytes, *, chunker: str = "fixed", chunk_size: int = 1024,
                        missing_fraction: float = 0.25, seed: int = 7) -> dict[str, float | int | bool]:
    sender_dictionary = build_dictionary(
        warm,
        chunker=chunker,
        chunk_size=chunk_size,
        max_chunks=redulink.MAX_DICT_CHUNKS,
    )
    receiver_dictionary = thin_dictionary(sender_dictionary, missing_fraction=missing_fraction, seed=seed)

    frames, initial_stats = redulink.encode(
        data,
        chunker=chunker,
        chunk_size=chunk_size,
        warm_dictionary=warm,
    )

    repaired_output: list[bytes] = []
    misses = 0
    repair_full_frames = 0
    repair_wire = 0
    delivered_ref_frames = 0
    delivered_full_frames = 0

    for frame in frames:
        if frame.kind == "FULL":
            if len(frame.payload) != frame.length or redulink.cid(frame.payload) != frame.cid:
                raise ValueError("invalid FULL frame")
            redulink.touch_lru(receiver_dictionary, frame.cid, frame.payload, redulink.MAX_DICT_CHUNKS)
            redulink.touch_lru(sender_dictionary, frame.cid, frame.payload, redulink.MAX_DICT_CHUNKS)
            repaired_output.append(frame.payload)
            delivered_full_frames += 1
            continue

        if frame.kind != "REF":
            raise ValueError(f"unknown frame kind: {frame.kind}")

        if frame.cid in receiver_dictionary and len(receiver_dictionary[frame.cid]) == frame.length:
            repaired_output.append(receiver_dictionary[frame.cid])
            delivered_ref_frames += 1
            continue

        misses += 1
        repair_payload = sender_dictionary.get(frame.cid)
        if repair_payload is None or len(repair_payload) != frame.length:
            raise ValueError("sender cannot repair missing REF")
        repair_frame = redulink.Frame("FULL", frame.cid, repair_payload, len(repair_payload))
        repair_wire += frame_wire_bytes(repair_frame)
        repair_full_frames += 1
        redulink.touch_lru(receiver_dictionary, frame.cid, repair_payload, redulink.MAX_DICT_CHUNKS)
        repaired_output.append(repair_payload)
        delivered_full_frames += 1

    reconstructed = b"".join(repaired_output)
    total_wire = initial_stats.wire_bytes + repair_wire
    return {
        "input_bytes": len(data),
        "initial_wire_bytes": initial_stats.wire_bytes,
        "repair_wire_bytes": repair_wire,
        "total_wire_bytes": total_wire,
        "initial_ref_frames": initial_stats.ref_frames,
        "initial_full_frames": initial_stats.full_frames,
        "misses": misses,
        "repair_full_frames": repair_full_frames,
        "delivered_ref_frames": delivered_ref_frames,
        "delivered_full_frames": delivered_full_frames,
        "effective_multiplier_after_repair": round((len(data) / total_wire) if total_wire else 1.0, 6),
        "receiver_missing_fraction": missing_fraction,
        "reconstruction_ok": reconstructed == data,
    }


def demo_payload() -> tuple[bytes, bytes]:
    base_chunks = [f"stable-block-{i:03d}:".encode() + (bytes([65 + i % 26]) * 1000) for i in range(32)]
    warm = b"".join(base_chunks)
    update_chunks = list(base_chunks)
    update_chunks[7] = b"changed-block-007:" + (b"Z" * 1000)
    update_chunks[19] = b"changed-block-019:" + (b"Y" * 1000)
    update = b"".join(update_chunks)
    return warm, update


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warm", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--chunker", choices=["fixed", "cdc"], default="fixed")
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--missing-fraction", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.warm and args.input:
        warm = args.warm.read_bytes()
        data = args.input.read_bytes()
    else:
        warm, data = demo_payload()

    result = semantic_repair_run(
        data,
        warm,
        chunker=args.chunker,
        chunk_size=args.chunk_size,
        missing_fraction=args.missing_fraction,
        seed=args.seed,
    )
    text = json.dumps(result, sort_keys=True, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    if not result["reconstruction_ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
