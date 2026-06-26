#!/usr/bin/env python3
"""Authenticated localhost UDP ReduLink endpoint experiment.

The earlier UDP prototype exercised semantic MISS/FULL repair over real sockets.
This authenticated UDP prototype adds artifact-level authentication semantics: every frame
is HMAC-bound to epoch, scope, stream id, reconstructed offset, cid, length,
nonce, and payload hash. The receiver verifies tags before accepting FULL or
REF frames, tracks nonces to reject replay, and repairs dictionary misses with
an authenticated FULL frame for the same reconstructed offset.

This remains a QUIC-adjacent endpoint experiment, not a native QUIC stack.
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
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_model as redulink
import redulink_secure as secure


def _json(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _send(sock: socket.socket, obj: dict[str, Any], addr: tuple[str, int]) -> int:
    payload = _json(obj)
    sock.sendto(payload, addr)
    return len(payload)


def _recv(sock: socket.socket) -> tuple[dict[str, Any], tuple[str, int], int]:
    payload, addr = sock.recvfrom(65535)
    return json.loads(payload.decode("utf-8")), addr, len(payload)


def frame_to_msg(frame: secure.SecureFrame) -> dict[str, Any]:
    msg = asdict(frame)
    msg["t"] = "FRAME"
    msg["payload_b64"] = base64.b64encode(frame.payload).decode("ascii")
    del msg["payload"]
    return msg


def msg_to_frame(msg: dict[str, Any]) -> secure.SecureFrame:
    return secure.SecureFrame(
        kind=str(msg["kind"]),
        epoch=int(msg["epoch"]),
        scope=str(msg["scope"]),
        stream_id=int(msg["stream_id"]),
        offset=int(msg["offset"]),
        cid=str(msg["cid"]),
        length=int(msg["length"]),
        nonce=int(msg["nonce"]),
        tag=str(msg["tag"]),
        payload=base64.b64decode(str(msg.get("payload_b64", "")).encode("ascii")),
    )


def build_secure_dictionary(data: bytes, *, secret: bytes, epoch: int, scope: str,
                            chunker: str, chunk_size: int) -> OrderedDict[str, bytes]:
    d: OrderedDict[str, bytes] = OrderedDict()
    for ch in redulink.make_chunks(data, chunker, chunk_size):
        redulink.touch_lru(d, secure.secure_cid(ch, secret=secret, epoch=epoch, scope=scope), ch, redulink.MAX_DICT_CHUNKS)
    return d


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


def make_full_repair(original_ref: secure.SecureFrame, payload: bytes, *, secret: bytes, nonce: int) -> secure.SecureFrame:
    tag = secure.frame_tag(
        secret=secret,
        kind="FULL",
        epoch=original_ref.epoch,
        scope=original_ref.scope,
        stream_id=original_ref.stream_id,
        offset=original_ref.offset,
        cid=original_ref.cid,
        length=len(payload),
        nonce=nonce,
        payload=payload,
    )
    return secure.SecureFrame(
        "FULL", original_ref.epoch, original_ref.scope, original_ref.stream_id,
        original_ref.offset, original_ref.cid, len(payload), nonce, tag, payload,
    )


class AuthUdpServer(threading.Thread):
    def __init__(self, *, warm: bytes, expected_sha256: str, secret: bytes, epoch: int, scope: str,
                 stream_id: int, chunker: str, chunk_size: int, missing_fraction: float, seed: int):
        super().__init__(daemon=True)
        self.secret = secret
        self.epoch = epoch
        self.scope = scope
        self.stream_id = stream_id
        self.expected_sha256 = expected_sha256
        self.chunker = chunker
        self.chunk_size = chunk_size
        full = build_secure_dictionary(warm, secret=secret, epoch=epoch, scope=scope, chunker=chunker, chunk_size=chunk_size)
        self.dictionary = thin_dictionary(full, missing_fraction=missing_fraction, seed=seed)
        self.initial_dictionary_entries = len(self.dictionary)
        self.ready = threading.Event()
        self.done = threading.Event()
        self.error: str | None = None
        self.stats: dict[str, Any] = {}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.address = self.sock.getsockname()

    def run(self) -> None:
        delivered: dict[int, bytes] = {}
        seen_nonces: set[int] = set()
        received = sent = auth_failures = replay_rejections = semantic_misses = repair_full = 0
        start = time.perf_counter()
        self.ready.set()
        try:
            self.sock.settimeout(5.0)
            while True:
                msg, addr, size = _recv(self.sock)
                received += size
                if msg.get("t") == "END":
                    output = b"".join(delivered[i] for i in sorted(delivered))
                    stats = {
                        "experiment": "authenticated_udp_repair",
                        "reconstruction_ok": hashlib.sha256(output).hexdigest() == self.expected_sha256,
                        "server_reconstructed_bytes": len(output),
                        "server_received_payload_bytes": received,
                        "server_sent_payload_bytes": sent,
                        "server_initial_dictionary_entries": self.initial_dictionary_entries,
                        "server_final_dictionary_entries": len(self.dictionary),
                        "auth_failures": auth_failures,
                        "replay_rejections": replay_rejections,
                        "semantic_misses": semantic_misses,
                        "repair_full_frames": repair_full,
                        "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3),
                    }
                    sent += _send(self.sock, {"t": "STATS", "stats": stats}, addr)
                    self.stats = stats
                    return
                if msg.get("t") != "FRAME":
                    sent += _send(self.sock, {"t": "ERROR", "error": "unknown message"}, addr)
                    continue
                frame = msg_to_frame(msg)
                seq = int(msg["seq"])
                try:
                    secure.verify_frame(
                        frame,
                        secret=self.secret,
                        expected_epoch=self.epoch,
                        expected_scope=self.scope,
                        expected_stream_id=self.stream_id,
                        expected_offset=frame.offset,
                        seen_nonces=seen_nonces,
                    )
                except ValueError as exc:
                    if "replayed" in str(exc):
                        replay_rejections += 1
                    else:
                        auth_failures += 1
                    sent += _send(self.sock, {"t": "ERROR", "seq": seq, "error": str(exc)}, addr)
                    continue
                seen_nonces.add(frame.nonce)
                if seq < 0:
                    # Negative sequence numbers are reserved for authentication/replay
                    # probes. They exercise the verifier without committing bytes to
                    # the reconstructed stream.
                    sent += _send(self.sock, {"t": "ACK", "seq": seq, "probe": True}, addr)
                    continue
                if frame.kind == "FULL":
                    if len(frame.payload) != frame.length:
                        auth_failures += 1
                        sent += _send(self.sock, {"t": "ERROR", "seq": seq, "error": "length mismatch"}, addr)
                        continue
                    if secure.secure_cid(frame.payload, secret=self.secret, epoch=self.epoch, scope=self.scope) != frame.cid:
                        auth_failures += 1
                        sent += _send(self.sock, {"t": "ERROR", "seq": seq, "error": "cid mismatch"}, addr)
                        continue
                    redulink.touch_lru(self.dictionary, frame.cid, frame.payload, redulink.MAX_DICT_CHUNKS)
                    delivered[seq] = frame.payload
                    if bool(msg.get("repair", False)):
                        repair_full += 1
                    sent += _send(self.sock, {"t": "ACK", "seq": seq}, addr)
                elif frame.kind == "REF":
                    chunk = self.dictionary.get(frame.cid)
                    if chunk is None or len(chunk) != frame.length:
                        semantic_misses += 1
                        sent += _send(self.sock, {"t": "MISS", "seq": seq, "cid": frame.cid, "length": frame.length}, addr)
                    else:
                        delivered[seq] = chunk
                        sent += _send(self.sock, {"t": "ACK", "seq": seq}, addr)
                else:
                    sent += _send(self.sock, {"t": "ERROR", "seq": seq, "error": "unknown kind"}, addr)
        except Exception as exc:  # pragma: no cover
            self.error = repr(exc)
        finally:
            self.done.set()
            self.sock.close()


def demo_payload() -> tuple[bytes, bytes]:
    base = []
    for i in range(64):
        label = f"auth-block-{i:03d}:".encode("ascii")
        base.append(label + bytes([65 + i % 26]) * (1024 - len(label)))
    warm = b"".join(base)
    update = list(base)
    for i, b in [(7, b"x"), (21, b"y"), (42, b"z")]:
        label = f"auth-changed-{i:03d}:".encode("ascii")
        update[i] = label + b * (1024 - len(label))
    return warm, b"".join(update)


def run_experiment(*, warm: bytes, data: bytes, missing_fraction: float = 0.20,
                   chunk_size: int = 1024, seed: int = 11,
                   inject_tamper_probe: bool = True, inject_replay_probe: bool = True) -> dict[str, Any]:
    secret = b"redulink-authenticated-udp-artifact-secret"
    epoch = 5
    scope = "artifact-auth-udp"
    stream_id = 1
    frames, initial = secure.encode(
        data, warm_dictionary=warm, secret=secret, epoch=epoch, scope=scope,
        stream_id=stream_id, chunker="fixed", chunk_size=chunk_size,
    )
    sender_dict = build_secure_dictionary(warm, secret=secret, epoch=epoch, scope=scope, chunker="fixed", chunk_size=chunk_size)
    server = AuthUdpServer(
        warm=warm, expected_sha256=hashlib.sha256(data).hexdigest(), secret=secret, epoch=epoch,
        scope=scope, stream_id=stream_id, chunker="fixed", chunk_size=chunk_size,
        missing_fraction=missing_fraction, seed=seed,
    )
    server.start()
    server.ready.wait(2.0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(2.0)
    client_sent = client_received = repairs = tamper_rejections = replay_rejections = 0
    next_nonce = max(f.nonce for f in frames) + 1

    def exchange(msg: dict[str, Any]) -> dict[str, Any]:
        nonlocal client_sent, client_received
        client_sent += _send(sock, msg, server.address)
        reply, _addr, size = _recv(sock)
        client_received += size
        return reply

    try:
        if inject_tamper_probe:
            probe = dict(frame_to_msg(frames[0]))
            probe["seq"] = -100
            probe["tag"] = "00" * secure.TAG_BYTES
            reply = exchange(probe)
            tamper_rejections += int(reply.get("t") == "ERROR")
        if inject_replay_probe:
            base = frames[0]
            probe_nonce = max(f.nonce for f in frames) + 1000
            probe_tag = secure.frame_tag(
                secret=secret, kind=base.kind, epoch=base.epoch, scope=base.scope,
                stream_id=base.stream_id, offset=base.offset, cid=base.cid,
                length=base.length, nonce=probe_nonce, payload=base.payload,
            )
            replay_probe = secure.SecureFrame(
                base.kind, base.epoch, base.scope, base.stream_id, base.offset,
                base.cid, base.length, probe_nonce, probe_tag, base.payload,
            )
            probe = dict(frame_to_msg(replay_probe))
            probe["seq"] = -99
            # First send valid probe, then replay the same nonce and tag.
            exchange(probe)
            reply = exchange(probe)
            replay_rejections += int(reply.get("t") == "ERROR")

        for seq, frame in enumerate(frames):
            msg = frame_to_msg(frame)
            msg["seq"] = seq
            reply = exchange(msg)
            if reply.get("t") == "MISS":
                payload = sender_dict.get(frame.cid)
                if payload is None:
                    raise RuntimeError("sender lacks repair chunk")
                repair = make_full_repair(frame, payload, secret=secret, nonce=next_nonce)
                next_nonce += 1
                rmsg = frame_to_msg(repair)
                rmsg["seq"] = seq
                rmsg["repair"] = True
                ack = exchange(rmsg)
                if ack.get("t") != "ACK":
                    raise RuntimeError(f"repair rejected: {ack}")
                repairs += 1
            elif reply.get("t") != "ACK":
                raise RuntimeError(f"unexpected reply: {reply}")
        end = {"t": "END", "sha256": hashlib.sha256(data).hexdigest()}
        client_sent += _send(sock, end, server.address)
        reply, _addr, size = _recv(sock)
        client_received += size
        stats = dict(reply["stats"])
    finally:
        sock.close()
    server.done.wait(2.0)
    if server.error:
        raise RuntimeError(server.error)
    stats.update({
        "input_bytes": len(data),
        "initial_model_wire_bytes": initial.wire_bytes,
        "initial_secure_effective_multiplier": round(initial.effective_multiplier, 6),
        "client_payload_bytes_sent": client_sent,
        "client_payload_bytes_received": client_received,
        "client_repair_full_frames": repairs,
        "tamper_probe_rejections": tamper_rejections,
        "replay_probe_rejections": replay_rejections,
        "socket_payload_multiplier": round(len(data) / client_sent, 6),
        "chunk_size": chunk_size,
        "receiver_missing_fraction": missing_fraction,
    })
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warm", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--missing-fraction", type=float, default=0.20)
    args = parser.parse_args()
    if args.warm and args.input:
        warm, data = args.warm.read_bytes(), args.input.read_bytes()
    else:
        warm, data = demo_payload()
    result = run_experiment(warm=warm, data=data, missing_fraction=args.missing_fraction)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    if not result.get("reconstruction_ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
