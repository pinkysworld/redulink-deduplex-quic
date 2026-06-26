#!/usr/bin/env python3
"""Local UDP ReduLink endpoint prototype with semantic MISS repair.

This prototype exercises real sockets on localhost. It is deliberately small:
a client sends modeled FULL/REF frames as UDP datagrams, the receiver starts
with an intentionally incomplete warm dictionary, missing REF frames trigger
MISS replies, and the client repairs those semantic misses with FULL repair
datagrams for the same reconstructed position. An optional deterministic drop
rule forces timeout/retransmission over UDP.

The experiment validates endpoint behavior, byte-exact reconstruction, semantic
repair, and retry handling. It is not a QUIC implementation and does not provide
production cryptographic authentication.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import random
import socket
import sys
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_model as redulink


def _json_bytes(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _send_json(sock: socket.socket, obj: dict[str, Any], addr: tuple[str, int]) -> int:
    payload = _json_bytes(obj)
    sock.sendto(payload, addr)
    return len(payload)


def _recv_json(sock: socket.socket) -> tuple[dict[str, Any], tuple[str, int], int]:
    payload, addr = sock.recvfrom(65535)
    return json.loads(payload.decode("utf-8")), addr, len(payload)


def build_dictionary(data: bytes, *, chunker: str, chunk_size: int) -> OrderedDict[str, bytes]:
    dictionary: OrderedDict[str, bytes] = OrderedDict()
    for chunk in redulink.make_chunks(data, chunker, chunk_size):
        redulink.touch_lru(dictionary, redulink.cid(chunk), chunk, redulink.MAX_DICT_CHUNKS)
    return dictionary


def thin_dictionary(dictionary: OrderedDict[str, bytes], *, missing_fraction: float, seed: int) -> OrderedDict[str, bytes]:
    rng = random.Random(seed)
    kept: OrderedDict[str, bytes] = OrderedDict()
    for key, value in dictionary.items():
        if rng.random() >= missing_fraction:
            kept[key] = value
    if dictionary and len(kept) == len(dictionary):
        first = next(iter(kept))
        del kept[first]
    return kept


def frame_to_message(seq: int, frame: redulink.Frame, *, repair: bool = False) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "t": "FRAME",
        "seq": seq,
        "kind": frame.kind,
        "cid": frame.cid,
        "length": frame.length,
        "repair": repair,
    }
    if frame.kind == "FULL":
        msg["payload_b64"] = base64.b64encode(frame.payload).decode("ascii")
    return msg


def frame_wire_bytes(frame: redulink.Frame) -> int:
    if frame.kind == "FULL":
        return redulink.FULL_OVERHEAD + len(frame.payload)
    if frame.kind == "REF":
        return redulink.REF_OVERHEAD
    raise ValueError(f"unknown frame kind: {frame.kind}")


class UdpRepairServer(threading.Thread):
    def __init__(self, *, warm: bytes, expected_sha256: str, chunker: str, chunk_size: int,
                 missing_fraction: float, seed: int, drop_every_nth_data: int = 0):
        super().__init__(daemon=True)
        self.expected_sha256 = expected_sha256
        self.chunker = chunker
        self.chunk_size = chunk_size
        self.drop_every_nth_data = drop_every_nth_data
        self.ready = threading.Event()
        self.done = threading.Event()
        self.error: str | None = None
        self.stats: dict[str, Any] = {}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.address = self.sock.getsockname()
        full_dictionary = build_dictionary(warm, chunker=chunker, chunk_size=chunk_size)
        self.dictionary = thin_dictionary(full_dictionary, missing_fraction=missing_fraction, seed=seed)
        self.initial_dictionary_entries = len(self.dictionary)

    def run(self) -> None:
        delivered: dict[int, bytes] = {}
        dropped_once: set[int] = set()
        attempts_by_seq: dict[int, int] = {}
        received_datagrams = 0
        received_payload_bytes = 0
        ack_datagrams = 0
        miss_datagrams = 0
        semantic_misses = 0
        repair_full_frames = 0
        dropped_datagrams = 0
        full_frames = 0
        ref_frames = 0
        start = time.perf_counter()
        self.ready.set()
        try:
            self.sock.settimeout(5.0)
            while True:
                msg, addr, size = _recv_json(self.sock)
                received_datagrams += 1
                received_payload_bytes += size
                typ = msg.get("t")
                if typ == "END":
                    output = b"".join(delivered[i] for i in sorted(delivered))
                    reconstruction_ok = hashlib.sha256(output).hexdigest() == self.expected_sha256
                    stats = {
                        "server_received_datagrams": received_datagrams,
                        "server_received_payload_bytes": received_payload_bytes,
                        "server_ack_datagrams": ack_datagrams,
                        "server_miss_datagrams": miss_datagrams,
                        "server_dropped_datagrams": dropped_datagrams,
                        "server_initial_dictionary_entries": self.initial_dictionary_entries,
                        "server_final_dictionary_entries": len(self.dictionary),
                        "server_delivered_frames": len(delivered),
                        "server_full_frames": full_frames,
                        "server_ref_frames": ref_frames,
                        "semantic_misses": semantic_misses,
                        "repair_full_frames": repair_full_frames,
                        "server_reconstructed_bytes": len(output),
                        "reconstruction_ok": reconstruction_ok,
                        "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3),
                    }
                    _send_json(self.sock, {"t": "STATS", "stats": stats}, addr)
                    self.stats = stats
                    return

                if typ != "FRAME":
                    _send_json(self.sock, {"t": "ERROR", "error": "unknown message type"}, addr)
                    continue

                seq = int(msg["seq"])
                attempts_by_seq[seq] = attempts_by_seq.get(seq, 0) + 1
                if (self.drop_every_nth_data > 0 and seq > 0 and seq % self.drop_every_nth_data == 0
                        and seq not in dropped_once):
                    dropped_once.add(seq)
                    dropped_datagrams += 1
                    continue

                if seq in delivered:
                    _send_json(self.sock, {"t": "ACK", "seq": seq, "duplicate": True}, addr)
                    ack_datagrams += 1
                    continue

                kind = msg["kind"]
                cid = msg["cid"]
                length = int(msg["length"])
                if kind == "FULL":
                    payload = base64.b64decode(msg["payload_b64"].encode("ascii"))
                    if len(payload) != length or redulink.cid(payload) != cid:
                        _send_json(self.sock, {"t": "ERROR", "seq": seq, "error": "FULL validation failed"}, addr)
                        continue
                    redulink.touch_lru(self.dictionary, cid, payload, redulink.MAX_DICT_CHUNKS)
                    delivered[seq] = payload
                    full_frames += 1
                    if bool(msg.get("repair", False)):
                        repair_full_frames += 1
                    _send_json(self.sock, {"t": "ACK", "seq": seq}, addr)
                    ack_datagrams += 1
                    continue

                if kind == "REF":
                    chunk = self.dictionary.get(cid)
                    if chunk is None or len(chunk) != length:
                        semantic_misses += 1
                        _send_json(self.sock, {"t": "MISS", "seq": seq, "cid": cid, "length": length}, addr)
                        miss_datagrams += 1
                        continue
                    delivered[seq] = chunk
                    ref_frames += 1
                    _send_json(self.sock, {"t": "ACK", "seq": seq}, addr)
                    ack_datagrams += 1
                    continue

                _send_json(self.sock, {"t": "ERROR", "seq": seq, "error": "unknown frame kind"}, addr)
        except Exception as exc:  # pragma: no cover - surfaced to caller
            self.error = repr(exc)
        finally:
            self.done.set()
            self.sock.close()


def demo_payload() -> tuple[bytes, bytes]:
    def block(label: str, fill: bytes, size: int = 1024) -> bytes:
        prefix = label.encode("ascii")
        if len(prefix) > size:
            raise ValueError("demo block label too long")
        return prefix + (fill * (size - len(prefix)))

    base_chunks = [block(f"stable-udp-block-{i:03d}:", bytes([65 + i % 26])) for i in range(48)]
    warm = b"".join(base_chunks)
    update_chunks = list(base_chunks)
    for idx, byte in [(5, b"Z"), (17, b"Y"), (33, b"X")]:
        update_chunks[idx] = block(f"changed-udp-block-{idx:03d}:", byte)
    update = b"".join(update_chunks)
    return warm, update


def run_udp_repair_experiment(*, warm: bytes, data: bytes, chunker: str = "fixed", chunk_size: int = 1024,
                              missing_fraction: float = 0.25, seed: int = 7,
                              drop_every_nth_data: int = 0, timeout: float = 0.05,
                              max_retries: int = 6) -> dict[str, Any]:
    sender_dictionary = build_dictionary(warm, chunker=chunker, chunk_size=chunk_size)
    frames, initial_stats = redulink.encode(data, chunker=chunker, chunk_size=chunk_size, warm_dictionary=warm)
    expected_sha256 = hashlib.sha256(data).hexdigest()

    server = UdpRepairServer(
        warm=warm,
        expected_sha256=expected_sha256,
        chunker=chunker,
        chunk_size=chunk_size,
        missing_fraction=missing_fraction,
        seed=seed,
        drop_every_nth_data=drop_every_nth_data,
    )
    server.start()
    server.ready.wait(2.0)

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_sock.bind(("127.0.0.1", 0))
    client_sock.settimeout(timeout)

    client_datagrams_sent = 0
    client_payload_bytes_sent = 0
    client_payload_bytes_received = 0
    retransmissions = 0
    client_miss_replies = 0
    client_ack_replies = 0
    repair_full_frames = 0
    repair_wire_model_bytes = 0
    start = time.perf_counter()

    def send_and_wait_ack(seq: int, msg: dict[str, Any]) -> dict[str, Any]:
        nonlocal client_datagrams_sent, client_payload_bytes_sent, client_payload_bytes_received
        nonlocal retransmissions, client_miss_replies, client_ack_replies
        attempts = 0
        while attempts <= max_retries:
            if attempts > 0:
                retransmissions += 1
            client_payload_bytes_sent += _send_json(client_sock, msg, server.address)
            client_datagrams_sent += 1
            try:
                reply, _addr, reply_size = _recv_json(client_sock)
                client_payload_bytes_received += reply_size
            except socket.timeout:
                attempts += 1
                continue
            if reply.get("t") == "ACK" and int(reply.get("seq", -1)) == seq:
                client_ack_replies += 1
                return reply
            if reply.get("t") == "MISS" and int(reply.get("seq", -1)) == seq:
                client_miss_replies += 1
                return reply
            if reply.get("t") == "ERROR":
                raise RuntimeError(reply.get("error", "server error"))
            attempts += 1
        raise TimeoutError(f"no ACK/MISS for seq {seq}")

    try:
        for seq, frame in enumerate(frames):
            reply = send_and_wait_ack(seq, frame_to_message(seq, frame))
            if reply.get("t") == "MISS":
                repair_payload = sender_dictionary.get(frame.cid)
                if repair_payload is None or len(repair_payload) != frame.length:
                    raise RuntimeError(f"sender cannot repair REF seq {seq}")
                repair = redulink.Frame("FULL", frame.cid, repair_payload, len(repair_payload))
                repair_full_frames += 1
                repair_wire_model_bytes += frame_wire_bytes(repair)
                ack = send_and_wait_ack(seq, frame_to_message(seq, repair, repair=True))
                if ack.get("t") != "ACK":
                    raise RuntimeError(f"repair seq {seq} did not ACK")

        end_msg = {"t": "END", "input_bytes": len(data), "sha256": expected_sha256}
        for attempt in range(max_retries + 1):
            if attempt > 0:
                retransmissions += 1
            client_payload_bytes_sent += _send_json(client_sock, end_msg, server.address)
            client_datagrams_sent += 1
            try:
                reply, _addr, reply_size = _recv_json(client_sock)
                client_payload_bytes_received += reply_size
            except socket.timeout:
                continue
            if reply.get("t") == "STATS":
                break
        else:
            raise TimeoutError("no final STATS from server")
    finally:
        client_sock.close()

    server.done.wait(2.0)
    if server.error:
        raise RuntimeError(server.error)

    elapsed_ms = round((time.perf_counter() - start) * 1000.0, 3)
    total_wire_model_bytes = initial_stats.wire_bytes + repair_wire_model_bytes
    result: dict[str, Any] = {
        "experiment": "localhost_udp_semantic_repair",
        "input_bytes": len(data),
        "initial_model_wire_bytes": initial_stats.wire_bytes,
        "repair_model_wire_bytes": repair_wire_model_bytes,
        "total_model_wire_bytes": total_wire_model_bytes,
        "model_effective_multiplier_after_repair": round(len(data) / total_wire_model_bytes, 6),
        "client_udp_datagrams_sent": client_datagrams_sent,
        "client_payload_bytes_sent": client_payload_bytes_sent,
        "client_payload_bytes_received": client_payload_bytes_received,
        "client_ack_replies": client_ack_replies,
        "client_miss_replies": client_miss_replies,
        "client_retransmissions": retransmissions,
        "client_repair_full_frames": repair_full_frames,
        "socket_payload_multiplier": round(len(data) / client_payload_bytes_sent, 6),
        "chunker": chunker,
        "chunk_size": chunk_size,
        "receiver_missing_fraction": missing_fraction,
        "drop_every_nth_data": drop_every_nth_data,
        "client_elapsed_ms": elapsed_ms,
    }
    result.update(server.stats)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warm", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--chunker", choices=["fixed", "cdc"], default="fixed")
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--missing-fraction", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--drop-every-nth-data", type=int, default=7)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.warm and args.input:
        warm = args.warm.read_bytes()
        data = args.input.read_bytes()
    else:
        warm, data = demo_payload()

    result = run_udp_repair_experiment(
        warm=warm,
        data=data,
        chunker=args.chunker,
        chunk_size=args.chunk_size,
        missing_fraction=args.missing_fraction,
        seed=args.seed,
        drop_every_nth_data=args.drop_every_nth_data,
    )
    text = json.dumps(result, sort_keys=True, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    if not result.get("reconstruction_ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
