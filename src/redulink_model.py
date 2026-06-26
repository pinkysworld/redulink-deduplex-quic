#!/usr/bin/env python3
"""
ReduLink encoder/decoder artifact model.

This script models ReduLink's payload representation layer. It splits input
bytes into chunks, emits FULL frames for new chunks, emits REF frames for chunks
already available to the receiver, and verifies byte-exact reconstruction.

The accounting is conservative: FULL and REF frames include fixed framing
overhead, and random data should not produce useful savings.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import random
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

FULL_OVERHEAD = 24
REF_OVERHEAD = 32
DEFAULT_CHUNK = 8192
MAX_DICT_CHUNKS = 8192


@dataclass
class Frame:
    kind: str
    cid: str
    payload: bytes
    length: int


@dataclass
class Stats:
    input_bytes: int
    wire_bytes: int
    chunks: int
    full_frames: int
    ref_frames: int
    saving_rate: float
    effective_multiplier: float
    reconstruction_ok: bool


def cid(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:32]


def iter_files(path: Path) -> Iterable[tuple[Path, str]]:
    if path.is_file():
        yield path, path.name
        return
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'__pycache__', '.git'}]
        for name in sorted(files):
            p = Path(root) / name
            if p.is_file() and p.stat().st_size > 0:
                yield p, p.relative_to(path).as_posix()


def read_artifact(path: Path, limit_mib: int | None = None) -> bytes:
    if path.is_file():
        data = path.read_bytes()
        if limit_mib is not None:
            data = data[:limit_mib * 1024 * 1024]
        return data

    parts: List[bytes] = []
    remaining = None if limit_mib is None else limit_mib * 1024 * 1024
    for file, relative_name in iter_files(path):
        data = file.read_bytes()
        if remaining is not None:
            if remaining <= 0:
                break
            data = data[:remaining]
            remaining -= len(data)
        parts.append(b'\n---REDULINK-FILE-BOUNDARY---\n')
        parts.append(relative_name.encode('utf-8', 'replace'))
        parts.append(b'\n')
        parts.append(data)
    return b''.join(parts)


def fixed_chunks(data: bytes, size: int = DEFAULT_CHUNK) -> List[bytes]:
    return [data[i:i + size] for i in range(0, len(data), size)]


def cdc_chunks(data: bytes, target: int = DEFAULT_CHUNK, min_size: int = 2048, max_size: int = 32768) -> List[bytes]:
    """Return simple rolling-hash content-defined chunks."""
    if not data:
        return []
    mask = target - 1
    chunks: List[bytes] = []
    start = 0
    h = 0
    for i, b in enumerate(data):
        h = ((h << 1) + b + 0x9E3779B1) & 0xFFFFFFFF
        size = i - start + 1
        if size >= min_size and ((h & mask) == 0 or size >= max_size):
            chunks.append(data[start:i + 1])
            start = i + 1
            h = 0
    if start < len(data):
        chunks.append(data[start:])
    return chunks


def make_chunks(data: bytes, chunker: str, chunk_size: int) -> List[bytes]:
    if chunker == 'fixed':
        return fixed_chunks(data, chunk_size)
    if chunker == 'cdc':
        return cdc_chunks(data, chunk_size)
    raise ValueError(f'unknown chunker: {chunker}')


def touch_lru(cache: OrderedDict[str, bytes], key: str, value: bytes, max_chunks: int) -> None:
    if key in cache:
        cache.move_to_end(key)
    cache[key] = value
    while len(cache) > max_chunks:
        cache.popitem(last=False)


def encode(data: bytes, *, chunker: str = 'cdc', chunk_size: int = DEFAULT_CHUNK,
           warm_dictionary: bytes = b'', max_dict_chunks: int = MAX_DICT_CHUNKS,
           miss_rate: float = 0.0) -> Tuple[List[Frame], Stats]:
    dictionary: OrderedDict[str, bytes] = OrderedDict()
    for ch in make_chunks(warm_dictionary, chunker, chunk_size):
        touch_lru(dictionary, cid(ch), ch, max_dict_chunks)

    frames: List[Frame] = []
    wire = 0
    full = 0
    ref = 0

    for ch in make_chunks(data, chunker, chunk_size):
        k = cid(ch)
        can_ref = k in dictionary and random.random() >= miss_rate
        if can_ref:
            frames.append(Frame('REF', k, b'', len(ch)))
            wire += REF_OVERHEAD
            ref += 1
        else:
            frames.append(Frame('FULL', k, ch, len(ch)))
            wire += FULL_OVERHEAD + len(ch)
            full += 1
            touch_lru(dictionary, k, ch, max_dict_chunks)

    saving = max(0.0, 1.0 - wire / len(data)) if data else 0.0
    mult = (len(data) / wire) if wire else 1.0
    stats = Stats(
        input_bytes=len(data), wire_bytes=wire, chunks=len(frames),
        full_frames=full, ref_frames=ref, saving_rate=saving,
        effective_multiplier=mult, reconstruction_ok=False,
    )
    return frames, stats


def decode(frames: List[Frame], *, warm_dictionary: bytes = b'', chunker: str = 'cdc',
           chunk_size: int = DEFAULT_CHUNK, max_dict_chunks: int = MAX_DICT_CHUNKS) -> bytes:
    dictionary: OrderedDict[str, bytes] = OrderedDict()
    for ch in make_chunks(warm_dictionary, chunker, chunk_size):
        touch_lru(dictionary, cid(ch), ch, max_dict_chunks)

    out: List[bytes] = []
    for fr in frames:
        if fr.kind == 'FULL':
            if len(fr.payload) != fr.length:
                raise ValueError('FULL frame length mismatch')
            if cid(fr.payload) != fr.cid:
                raise ValueError('FULL frame failed chunk-id validation')
            touch_lru(dictionary, fr.cid, fr.payload, max_dict_chunks)
            out.append(fr.payload)
        elif fr.kind == 'REF':
            if fr.cid not in dictionary:
                raise ValueError('REF miss: receiver lacks referenced chunk')
            chunk = dictionary[fr.cid]
            if len(chunk) != fr.length:
                raise ValueError('REF frame length mismatch')
            out.append(chunk)
        else:
            raise ValueError(f'unknown frame kind: {fr.kind}')
    return b''.join(out)


def run_bytes(data: bytes, *, chunker: str, chunk_size: int, warm: bytes = b'', miss_rate: float = 0.0) -> Stats:
    frames, stats = encode(data, chunker=chunker, chunk_size=chunk_size, warm_dictionary=warm, miss_rate=miss_rate)
    reconstructed = decode(frames, warm_dictionary=warm, chunker=chunker, chunk_size=chunk_size)
    stats.reconstruction_ok = reconstructed == data
    return stats


def print_stats(label: str, stats: Stats) -> None:
    print(f'family,mode,input_bytes,wire_model_bytes,saving_rate,effective_multiplier,chunks,full_frames,ref_frames,reconstruction_ok')
    print(','.join([
        label,
        'model',
        str(stats.input_bytes),
        str(stats.wire_bytes),
        f'{stats.saving_rate:.6f}',
        f'{stats.effective_multiplier:.6f}',
        str(stats.chunks),
        str(stats.full_frames),
        str(stats.ref_frames),
        str(stats.reconstruction_ok),
    ]))


def cmd_artifact(args: argparse.Namespace) -> None:
    path = Path(args.path)
    data = read_artifact(path, args.limit_mib)
    if args.mode == 'cold':
        warm = b''
    else:
        # Warm mode uses an earlier related prefix as receiver dictionary state.
        cut = max(1, int(len(data) * args.warm_fraction))
        warm = data[:cut]
        data = data[cut:]
    stats = run_bytes(data, chunker=args.chunker, chunk_size=args.chunk_size, warm=warm, miss_rate=args.miss_rate)
    print_stats(path.name or 'artifact', stats)


def cmd_random(args: argparse.Namespace) -> None:
    rng = random.Random(args.seed)
    data = bytes(rng.getrandbits(8) for _ in range(args.size_mib * 1024 * 1024))
    stats = run_bytes(data, chunker=args.chunker, chunk_size=args.chunk_size, miss_rate=args.miss_rate)
    print_stats('random-negative-control', stats)


def cmd_synthetic(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    base_lines = [
        f'INFO service=api tenant={i % 32} status=200 template=login latency={i % 97}\n'.encode()
        for i in range(50000)
    ]
    data = b''.join(base_lines)
    if args.variant == 'logs':
        pass
    elif args.variant == 'updates':
        data = data + data[: len(data) // 2]
    elif args.variant == 'mixed':
        rng = random.Random(args.seed)
        data = data + bytes(rng.getrandbits(8) for _ in range(len(data) // 4))
    stats = run_bytes(data, chunker=args.chunker, chunk_size=args.chunk_size, miss_rate=args.miss_rate)
    print_stats(args.variant, stats)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='ReduLink encoder/decoder artifact model')
    sub = p.add_subparsers(required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--chunker', choices=['cdc', 'fixed'], default='cdc')
    common.add_argument('--chunk-size', type=int, default=DEFAULT_CHUNK)
    common.add_argument('--miss-rate', type=float, default=0.0)
    common.add_argument('--seed', type=int, default=7)

    a = sub.add_parser('artifact', parents=[common], help='run on a file or directory')
    a.add_argument('--path', required=True)
    a.add_argument('--mode', choices=['cold', 'warm'], default='cold')
    a.add_argument('--warm-fraction', type=float, default=0.45)
    a.add_argument('--limit-mib', type=int, default=None)
    a.set_defaults(func=cmd_artifact)

    r = sub.add_parser('random', parents=[common], help='negative random-data control')
    r.add_argument('--size-mib', type=int, default=8)
    r.set_defaults(func=cmd_random)

    s = sub.add_parser('synthetic', parents=[common], help='synthetic workload')
    s.add_argument('--variant', choices=['logs', 'updates', 'mixed'], default='logs')
    s.set_defaults(func=cmd_synthetic)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
