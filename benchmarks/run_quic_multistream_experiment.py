#!/usr/bin/env python3
"""Measure ReduLink object isolation across real QUIC streams on one connection.

A miss-heavy large object and several small warm-hit objects share one live
TLS 1.3 / QUIC connection. The benchmark compares concurrent independent QUIC
streams with sequential streams on the same connection. Every stream derives a
distinct ReduLink key from the live exporter and actual QUIC stream ID.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import platform
import secrets
import ssl
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "prototypes"))

from aioquic.asyncio import connect, serve  # type: ignore
from aioquic.quic.configuration import QuicConfiguration  # type: ignore

from stats_utils import bootstrap_ci, mean, round_float  # type: ignore
from redulink_aioquic_experiment import (  # type: ignore
    ALPN,
    PROTOCOL_VERSION,
    QuicReduLinkServer,
    SEND_DRAIN_BYTES,
    build_secure_dictionary,
    demo_payload,
    frame_to_msg,
    key_schedule,
    make_full_repair,
    read_msg,
    send_msg,
    send_msgs_batched,
    secure,
    tls_exporter,
    validate_missing_items,
    wire,
    write_self_signed_cert,
)


@dataclass(frozen=True)
class ObjectSpec:
    name: str
    role: str
    warm: bytes
    data: bytes
    missing_every: int


def make_specs(*, blocker_blocks: int, small_blocks: int, small_count: int) -> list[ObjectSpec]:
    blocker_warm, blocker_data = demo_payload(blocker_blocks)
    small_warm, small_data = demo_payload(small_blocks)
    return [
        ObjectSpec(
            name="blocker",
            role="miss-heavy-large",
            warm=blocker_warm,
            data=blocker_data,
            missing_every=1,
        ),
        *[
            ObjectSpec(
                name=f"small-{index + 1}",
                role="warm-hit-small",
                warm=small_warm,
                data=small_data,
                missing_every=0,
            )
            for index in range(small_count)
        ],
    ]


def stream_secret(
    *,
    exporter_output: bytes,
    connection_context: bytes,
    stream_id: int,
    epoch: int,
    scope: str,
) -> bytes:
    return key_schedule.derive_redulink_secret(
        exporter_output,
        key_schedule.ReduLinkKeyContext(
            alpn=ALPN[0],
            epoch=epoch,
            scope=scope,
            connection_context=connection_context,
            stream_context=stream_id.to_bytes(8, "big"),
            direction="client-to-server",
        ),
    )


async def transfer_object(
    *,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    spec: ObjectSpec,
    exporter_output: bytes,
    connection_context: bytes,
    epoch: int,
    scope: str,
    session_started: float,
    stream_started_event: asyncio.Event | None = None,
) -> dict[str, Any]:
    stream_started = time.perf_counter()
    stream_id = int(writer.get_extra_info("stream_id"))
    secret = stream_secret(
        exporter_output=exporter_output,
        connection_context=connection_context,
        stream_id=stream_id,
        epoch=epoch,
        scope=scope,
    )
    frames, initial = secure.encode(
        spec.data,
        warm_dictionary=spec.warm,
        secret=secret,
        epoch=epoch,
        scope=scope,
        stream_id=stream_id,
        chunker="fixed",
        chunk_size=1024,
    )
    sender_dictionary = build_secure_dictionary(
        spec.warm,
        secret=secret,
        epoch=epoch,
        scope=scope,
        chunker="fixed",
        chunk_size=1024,
    )
    response_queue: asyncio.Queue[tuple[dict[str, Any], int, float] | BaseException] = asyncio.Queue()

    async def collect_responses() -> None:
        try:
            while True:
                response, size = await read_msg(reader)
                await response_queue.put((response, size, time.perf_counter()))
                if response.get("t") in {"STATS", "ERROR"}:
                    return
        except BaseException as exc:
            await response_queue.put(exc)

    async def next_response() -> tuple[dict[str, Any], int, float]:
        item = await response_queue.get()
        if isinstance(item, BaseException):
            raise item
        return item

    response_task = asyncio.create_task(collect_responses())
    forward_bytes = 0
    reverse_bytes = 0
    measurement_bytes = 0
    diagnostic_bytes = 0
    first_byte_at: float | None = None
    forward_bytes += await send_msg(writer, {
        "t": "HELLO",
        "version": PROTOCOL_VERSION,
        "input_sha256": hashlib.sha256(spec.data).hexdigest(),
        "input_length": len(spec.data),
        "chunk_size": 1024,
        "frame_count": len(frames),
    })
    if stream_started_event is not None:
        stream_started_event.set()
    forward_bytes += await send_msgs_batched(
        writer,
        (frame_to_msg(sequence, frame) for sequence, frame in enumerate(frames)),
    )
    forward_bytes += await send_msg(writer, {"t": "END_ROUND"})

    missing_items: list[dict[str, Any]] | None = None
    while missing_items is None:
        reply, size, received_at = await next_response()
        if reply.get("t") == "FIRST_BYTE":
            if first_byte_at is not None or int(reply.get("offset", -1)) != 0:
                raise RuntimeError("invalid FIRST_BYTE response")
            first_byte_at = received_at
            measurement_bytes += size
        elif reply.get("t") == "MISSING":
            missing_items = list(reply.get("items", []))
            reverse_bytes += size
        elif reply.get("t") == "ERROR":
            raise RuntimeError(str(reply.get("error", "server error")))
        else:
            raise RuntimeError(f"unexpected pre-repair response: {reply!r}")

    next_nonce = max((frame.nonce for frame in frames), default=0) + 1
    repairs = validate_missing_items(missing_items, frames)
    repair_messages = []
    for sequence, reference in repairs:
        payload = sender_dictionary.get(reference.cid)
        if payload is None:
            raise RuntimeError(f"missing repair payload for sequence {sequence}")
        repair = make_full_repair(reference, payload, secret=secret, nonce=next_nonce)
        next_nonce += 1
        repair_messages.append(frame_to_msg(sequence, repair, repair=True))
    forward_bytes += await send_msgs_batched(writer, repair_messages)
    forward_bytes += await send_msg(writer, {"t": "FINISH"})

    server_stats: dict[str, Any] | None = None
    while server_stats is None:
        reply, size, received_at = await next_response()
        if reply.get("t") == "FIRST_BYTE":
            if first_byte_at is not None or int(reply.get("offset", -1)) != 0:
                raise RuntimeError("invalid FIRST_BYTE response")
            first_byte_at = received_at
            measurement_bytes += size
        elif reply.get("t") == "STATS":
            diagnostic_bytes = size
            server_stats = dict(reply["stats"])
        elif reply.get("t") == "ERROR":
            raise RuntimeError(str(reply.get("error", "server error")))
        else:
            raise RuntimeError(f"unexpected post-repair response: {reply!r}")
    await response_task
    completed_at = time.perf_counter()
    if first_byte_at is None:
        raise RuntimeError("logical offset zero was never acknowledged")
    server_exporter_hash = str(server_stats.pop("tls_exporter_output_sha256", ""))
    exporter_outputs_match = hmac.compare_digest(
        server_exporter_hash,
        hashlib.sha256(exporter_output).hexdigest(),
    )
    if not exporter_outputs_match or not server_stats.get("reconstruction_ok"):
        raise RuntimeError("exporter mismatch or failed reconstruction")
    try:
        writer.write_eof()
        await writer.drain()
    except Exception:
        pass
    writer.close()
    return {
        "object": spec.name,
        "role": spec.role,
        "stream_id": stream_id,
        "input_bytes": len(spec.data),
        "initial_ref_frames": initial.ref_frames,
        "initial_full_frames": initial.full_frames,
        "semantic_misses": int(server_stats["semantic_misses"]),
        "repair_full_frames": len(repairs),
        "forward_protocol_stream_bytes": forward_bytes,
        "reverse_repair_control_stream_bytes": reverse_bytes,
        "measurement_control_stream_bytes_excluded": measurement_bytes,
        "diagnostic_stats_stream_bytes_excluded": diagnostic_bytes,
        "client_ttfb_from_session_ms": round((first_byte_at - session_started) * 1000.0, 3),
        "client_completion_from_session_ms": round((completed_at - session_started) * 1000.0, 3),
        "client_stream_duration_ms": round((completed_at - stream_started) * 1000.0, 3),
        "server_completion_ms": float(server_stats["server_completion_ms"]),
        "reconstruction_ok": bool(server_stats["reconstruction_ok"]),
        "tls_exporter_live": True,
        "tls_exporter_outputs_match": exporter_outputs_match,
        "sender_drain_batch_bytes": SEND_DRAIN_BYTES,
    }


async def run_mode(
    *,
    mode: str,
    specs: list[ObjectSpec],
    congestion_control_algorithm: str,
) -> dict[str, Any]:
    if mode not in {"multiplexed", "sequential"}:
        raise ValueError("mode must be multiplexed or sequential")
    epoch = 7
    scope = "artifact-multistream"
    application_session_id = secrets.token_bytes(32)
    client_connection_context = key_schedule.derive_connection_context(
        alpn=ALPN[0], application_session_id=application_session_id,
    )
    server_connection_context = key_schedule.derive_connection_context(
        alpn=ALPN[0], application_session_id=application_session_id,
    )
    exporter_context = key_schedule.tls_exporter_context(
        alpn=ALPN[0], scope=scope, connection_context=client_connection_context,
    )
    server_tasks: list[asyncio.Task[None]] = []
    with tempfile.TemporaryDirectory(prefix="redulink-multistream-") as temporary:
        cert_path, key_path = write_self_signed_cert(Path(temporary))
        server_configuration = QuicConfiguration(is_client=False, alpn_protocols=ALPN)
        server_configuration.congestion_control_algorithm = congestion_control_algorithm
        server_configuration.load_cert_chain(str(cert_path), str(key_path))
        client_configuration = QuicConfiguration(is_client=True, alpn_protocols=ALPN)
        client_configuration.congestion_control_algorithm = congestion_control_algorithm
        client_configuration.verify_mode = ssl.CERT_REQUIRED
        client_configuration.cafile = str(cert_path)

        def stream_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            stream_id = int(writer.get_extra_info("stream_id"))
            if stream_id % 4 != 0 or stream_id // 4 >= len(specs):
                raise RuntimeError(f"unexpected client bidirectional stream ID {stream_id}")
            spec = specs[stream_id // 4]
            server_exporter_output = tls_exporter.export_keying_material(
                tls_exporter.tls_context_from_stream_writer(writer),
                context_value=exporter_context,
                length=key_schedule.HASH_LEN,
            )
            state = QuicReduLinkServer(
                warm=spec.warm,
                expected_sha256=hashlib.sha256(spec.data).hexdigest(),
                expected_length=len(spec.data),
                secret=stream_secret(
                    exporter_output=server_exporter_output,
                    connection_context=server_connection_context,
                    stream_id=stream_id,
                    epoch=epoch,
                    scope=scope,
                ),
                epoch=epoch,
                scope=scope,
                stream_id=stream_id,
                chunker="fixed",
                chunk_size=1024,
                missing_every=spec.missing_every,
                tls_exporter_output_sha256=hashlib.sha256(server_exporter_output).hexdigest(),
            )
            server_tasks.append(asyncio.create_task(state.handle_stream(reader, writer)))

        server = await serve(
            "127.0.0.1", 0, configuration=server_configuration, stream_handler=stream_handler,
        )
        assert server._transport is not None
        port = int(server._transport.get_extra_info("sockname")[1])
        session_started = time.perf_counter()
        process_cpu_started = time.process_time()
        rows: list[dict[str, Any]] = []
        try:
            async with connect(
                "127.0.0.1", port, configuration=client_configuration, wait_connected=True,
            ) as protocol:
                client_exporter_output = tls_exporter.export_keying_material(
                    tls_exporter.tls_context_from_protocol(protocol),
                    context_value=exporter_context,
                    length=key_schedule.HASH_LEN,
                )
                if mode == "multiplexed":
                    transfer_tasks = []
                    for spec in specs:
                        reader, writer = await protocol.create_stream()
                        stream_started_event = asyncio.Event()
                        transfer_tasks.append(asyncio.create_task(transfer_object(
                            reader=reader,
                            writer=writer,
                            spec=spec,
                            exporter_output=client_exporter_output,
                            connection_context=client_connection_context,
                            epoch=epoch,
                            scope=scope,
                            session_started=session_started,
                            stream_started_event=stream_started_event,
                        )))
                        # aioquic advances the next stream ID when the first stream
                        # bytes are queued, not when create_stream() is called.
                        await stream_started_event.wait()
                    rows = await asyncio.gather(*transfer_tasks)
                else:
                    for spec in specs:
                        reader, writer = await protocol.create_stream()
                        rows.append(await transfer_object(
                            reader=reader,
                            writer=writer,
                            spec=spec,
                            exporter_output=client_exporter_output,
                            connection_context=client_connection_context,
                            epoch=epoch,
                            scope=scope,
                            session_started=session_started,
                        ))
                protocol.close()
            await asyncio.gather(*server_tasks)
        finally:
            server.close()
        completed_at = time.perf_counter()
        process_cpu_completed = time.process_time()
    for row in rows:
        row["mode"] = mode
    return {
        "mode": mode,
        "session_completion_ms": round((completed_at - session_started) * 1000.0, 3),
        "combined_endpoint_process_cpu_ms": round(
            (process_cpu_completed - process_cpu_started) * 1000.0, 3,
        ),
        "connection_contexts_match": hmac.compare_digest(
            client_connection_context, server_connection_context,
        ),
        "actual_stream_ids": [row["stream_id"] for row in rows],
        "rows": rows,
    }


def summarize_round(round_id: int, modes: list[dict[str, Any]]) -> dict[str, Any]:
    by_mode = {mode["mode"]: mode for mode in modes}
    multiplexed = by_mode["multiplexed"]
    sequential = by_mode["sequential"]

    def small_completion(mode: dict[str, Any]) -> list[float]:
        return [
            float(row["client_completion_from_session_ms"])
            for row in mode["rows"]
            if row["role"] == "warm-hit-small"
        ]

    def blocker_completion(mode: dict[str, Any]) -> float:
        return next(
            float(row["client_completion_from_session_ms"])
            for row in mode["rows"]
            if row["role"] == "miss-heavy-large"
        )

    multiplexed_small = small_completion(multiplexed)
    sequential_small = small_completion(sequential)
    multiplexed_blocker = blocker_completion(multiplexed)
    sequential_blocker = blocker_completion(sequential)
    return {
        "round": round_id,
        "multiplexed_small_mean_completion_ms": round_float(mean(multiplexed_small)),
        "sequential_small_mean_completion_ms": round_float(mean(sequential_small)),
        "small_mean_completion_ratio": round_float(
            mean(multiplexed_small) / mean(sequential_small),
        ),
        "multiplexed_small_tail_completion_ms": round_float(max(multiplexed_small)),
        "sequential_small_tail_completion_ms": round_float(max(sequential_small)),
        "small_tail_completion_ratio": round_float(
            max(multiplexed_small) / max(sequential_small),
        ),
        "multiplexed_blocker_completion_ms": round_float(multiplexed_blocker),
        "sequential_blocker_completion_ms": round_float(sequential_blocker),
        "blocker_completion_ratio": round_float(
            multiplexed_blocker / sequential_blocker,
        ),
        "multiplexed_session_completion_ms": multiplexed["session_completion_ms"],
        "sequential_session_completion_ms": sequential["session_completion_ms"],
        "session_completion_ratio": round_float(
            multiplexed["session_completion_ms"] / sequential["session_completion_ms"],
        ),
        "multiplexed_small_streams_finishing_before_blocker": sum(
            completion < multiplexed_blocker for completion in multiplexed_small
        ),
        "small_stream_count": len(multiplexed_small),
        "all_reconstructed": all(
            row["reconstruction_ok"]
            for mode in modes
            for row in mode["rows"]
        ),
    }


async def run_experiment(
    *,
    rounds: int,
    blocker_blocks: int,
    small_blocks: int,
    small_count: int,
    congestion_control_algorithm: str,
) -> dict[str, Any]:
    specs = make_specs(
        blocker_blocks=blocker_blocks,
        small_blocks=small_blocks,
        small_count=small_count,
    )
    raw_modes = []
    round_summaries = []
    for round_id in range(1, rounds + 1):
        order = ["multiplexed", "sequential"] if round_id % 2 else ["sequential", "multiplexed"]
        modes = [
            await run_mode(
                mode=mode,
                specs=specs,
                congestion_control_algorithm=congestion_control_algorithm,
            )
            for mode in order
        ]
        for execution_order, mode in enumerate(modes, start=1):
            mode["round"] = round_id
            mode["execution_order"] = execution_order
            for row in mode["rows"]:
                row["round"] = round_id
                row["execution_order"] = execution_order
        raw_modes.extend(modes)
        round_summaries.append(summarize_round(round_id, modes))

    aggregate: dict[str, Any] = {
        "rounds": rounds,
        "all_reconstructed": all(item["all_reconstructed"] for item in round_summaries),
    }
    for field in (
        "small_mean_completion_ratio",
        "small_tail_completion_ratio",
        "blocker_completion_ratio",
        "session_completion_ratio",
    ):
        values = [float(item[field]) for item in round_summaries]
        low, high = bootstrap_ci(values)
        aggregate[f"{field}_mean"] = round_float(mean(values))
        aggregate[f"{field}_ci95_low"] = round_float(low)
        aggregate[f"{field}_ci95_high"] = round_float(high)
    aggregate["fraction_of_multiplexed_small_streams_finishing_before_blocker"] = round_float(
        sum(item["multiplexed_small_streams_finishing_before_blocker"] for item in round_summaries)
        / sum(item["small_stream_count"] for item in round_summaries),
    )
    import aioquic  # type: ignore

    return {
        "experiment": "live_quic_multistream_isolation_v3_17",
        "claim_scope": (
            "application completion isolation from independent QUIC streams on one live connection; "
            "not a claim about a custom QUIC frame, connection migration, or 0-RTT"
        ),
        "comparison": (
            "same ordered object set and one connection per mode; a miss-heavy large object is first; "
            "multiplexed mode runs all streams concurrently while sequential mode completes each stream "
            "before opening the next"
        ),
        "keying": (
            "one live TLS exporter output per connection, then per-stream ReduLink derivation using the "
            "actual QUIC stream ID"
        ),
        "parameters": {
            "rounds": rounds,
            "blocker_blocks": blocker_blocks,
            "small_blocks": small_blocks,
            "small_count": small_count,
            "chunk_size_bytes": 1024,
            "blocker_missing_every": 1,
            "small_missing_every": 0,
            "congestion_control_algorithm": congestion_control_algorithm,
        },
        "provenance": {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(),
            "python": sys.version,
            "aioquic_version": aioquic.__version__,
        },
        "aggregate": aggregate,
        "round_summary": round_summaries,
        "modes": raw_modes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--blocker-blocks", type=int, default=2048)
    parser.add_argument("--small-blocks", type=int, default=64)
    parser.add_argument("--small-count", type=int, default=4)
    parser.add_argument("--congestion-control", choices=["reno", "cubic"], default="reno")
    parser.add_argument(
        "--output-json", type=Path,
        default=ROOT / "results" / "quic_multistream_experiment_v3_17.json",
    )
    parser.add_argument(
        "--output-csv", type=Path,
        default=ROOT / "results" / "quic_multistream_experiment_v3_17.csv",
    )
    args = parser.parse_args()
    if args.rounds < 1 or args.small_count < 1:
        raise SystemExit("rounds and small-count must be positive")
    result = asyncio.run(run_experiment(
        rounds=args.rounds,
        blocker_blocks=args.blocker_blocks,
        small_blocks=args.small_blocks,
        small_count=args.small_count,
        congestion_control_algorithm=args.congestion_control,
    ))
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = [row for mode in result["modes"] for row in mode["rows"]]
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(result["aggregate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
