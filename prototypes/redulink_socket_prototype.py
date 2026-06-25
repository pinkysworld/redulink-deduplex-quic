#!/usr/bin/env python3
"""Minimal ReduLink socket prototype.

This is intentionally small: it demonstrates endpoint cooperation and
byte-exact reconstruction over a TCP socket. It is not a QUIC implementation and
does not implement cryptographic authentication, loss recovery, or replay
windows.
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import tempfile
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_proto_v0_5 as redulink


def read_exact(sock: socket.socket, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining:
        data = sock.recv(remaining)
        if not data:
            raise EOFError("socket closed while reading frame")
        chunks.append(data)
        remaining -= len(data)
    return b"".join(chunks)


def send_frame(sock: socket.socket, frame: redulink.Frame) -> int:
    header = json.dumps({
        "kind": frame.kind,
        "cid": frame.cid,
        "length": frame.length,
        "payload_len": len(frame.payload),
    }, separators=(",", ":")).encode("utf-8")
    blob = struct.pack("!I", len(header)) + header + frame.payload
    sock.sendall(blob)
    return len(blob)


def recv_frame(sock: socket.socket) -> redulink.Frame | None:
    prefix = sock.recv(4)
    if not prefix:
        return None
    if len(prefix) < 4:
        prefix += read_exact(sock, 4 - len(prefix))
    header_len = struct.unpack("!I", prefix)[0]
    header = json.loads(read_exact(sock, header_len).decode("utf-8"))
    payload = read_exact(sock, int(header["payload_len"]))
    return redulink.Frame(
        str(header["kind"]),
        str(header["cid"]),
        payload,
        int(header["length"]),
    )


def run_server(host: str, port: int, warm_path: Path, output_path: Path,
               chunker: str, chunk_size: int, ready: threading.Event | None = None) -> tuple[int, int]:
    warm = warm_path.read_bytes() if warm_path else b""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        actual_port = server.getsockname()[1]
        if ready is not None:
            ready.actual_port = actual_port  # type: ignore[attr-defined]
            ready.set()
        conn, _ = server.accept()
        with conn:
            frames = []
            wire = 0
            while True:
                frame = recv_frame(conn)
                if frame is None:
                    break
                frames.append(frame)
                wire += redulink.FULL_OVERHEAD + len(frame.payload) if frame.kind == "FULL" else redulink.REF_OVERHEAD
            reconstructed = redulink.decode(
                frames,
                warm_dictionary=warm,
                chunker=chunker,
                chunk_size=chunk_size,
            )
            output_path.write_bytes(reconstructed)
            conn.sendall(json.dumps({"frames": len(frames), "wire_model_bytes": wire}).encode("utf-8"))
            return len(reconstructed), wire


def run_client(host: str, port: int, input_path: Path, warm_path: Path,
               chunker: str, chunk_size: int) -> dict[str, int]:
    data = input_path.read_bytes()
    warm = warm_path.read_bytes() if warm_path else b""
    frames, stats = redulink.encode(data, chunker=chunker, chunk_size=chunk_size, warm_dictionary=warm)
    socket_wire = 0
    with socket.create_connection((host, port), timeout=10) as sock:
        for frame in frames:
            socket_wire += send_frame(sock, frame)
        sock.shutdown(socket.SHUT_WR)
        ack = sock.recv(4096)
    server_stats = json.loads(ack.decode("utf-8")) if ack else {}
    return {
        "input_bytes": stats.input_bytes,
        "wire_model_bytes": stats.wire_bytes,
        "socket_bytes": socket_wire,
        "frames": stats.chunks,
        "ref_frames": stats.ref_frames,
        "server_reconstructed_bytes": int(server_stats.get("frames", 0)),
    }


def run_demo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        warm = base / "warm.bin"
        update = base / "update.bin"
        out = base / "out.bin"
        warm.write_bytes((b"public artifact line\n" * 4096) + b"v1\n")
        update.write_bytes((b"public artifact line\n" * 4096) + b"v2\n")
        ready = threading.Event()
        server_thread = threading.Thread(
            target=run_server,
            args=("127.0.0.1", 0, warm, out, "fixed", 1024, ready),
            daemon=True,
        )
        server_thread.start()
        ready.wait(5)
        port = ready.actual_port  # type: ignore[attr-defined]
        client_stats = run_client("127.0.0.1", port, update, warm, "fixed", 1024)
        server_thread.join(5)
        ok = out.read_bytes() == update.read_bytes()
        print(json.dumps({"reconstruction_ok": ok, **client_stats}, sort_keys=True))
        if not ok:
            raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--chunker", choices=["fixed", "cdc"], default="fixed")
    common.add_argument("--chunk-size", type=int, default=8192)
    common.add_argument("--warm", type=Path, required=True)

    server = sub.add_parser("server", parents=[common])
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=9876)
    server.add_argument("--output", type=Path, required=True)

    client = sub.add_parser("client", parents=[common])
    client.add_argument("--host", default="127.0.0.1")
    client.add_argument("--port", type=int, default=9876)
    client.add_argument("--input", type=Path, required=True)

    sub.add_parser("demo")
    args = parser.parse_args()

    if hasattr(args, "output"):
        reconstructed, wire = run_server(args.host, args.port, args.warm, args.output, args.chunker, args.chunk_size)
        print(json.dumps({"reconstructed_bytes": reconstructed, "wire_model_bytes": wire}, sort_keys=True))
    elif hasattr(args, "input"):
        print(json.dumps(run_client(args.host, args.port, args.input, args.warm, args.chunker, args.chunk_size), sort_keys=True))
    else:
        run_demo()


if __name__ == "__main__":
    main()
