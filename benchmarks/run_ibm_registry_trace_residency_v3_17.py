#!/usr/bin/env python3
"""Replay bounded per-client blob residency over the FAST'18 IBM registry trace.

The source trace contains anonymized production registry requests. This runner
uses only successful full GET responses for blob URIs and models an exact-byte
LRU at each anonymized client within each data center. Files for the same day
are merged by timestamp before replay. A cache hit means that the same client
previously completed the same blob GET and the object survived the stated byte
budget. It does not imply current authorization, within-blob chunk similarity,
or a ReduLink transfer; those questions are deliberately evaluated elsewhere.
"""

from __future__ import annotations

import argparse
from collections import Counter, OrderedDict
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import heapq
import json
import platform
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator, TextIO

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ARCHIVE_SHA1 = "06c4d412f85e2a307556cbf6c046002ebf6acc29"
SOURCE_TRACE_URL = "https://drive.google.com/file/d/1FjgyCJ8YayOKeMlxtbznhsiXGPYC9yP8/view"
SOURCE_PAPER_URL = "https://www.usenix.org/conference/fast18/presentation/anwar"
DATE_PATTERN = re.compile(r"logstash-(\d{4}\.\d{2}\.\d{2})-\d+\.json$")
DEFAULT_BUDGETS = [64 * 1024 * 1024, 256 * 1024 * 1024, 1024 * 1024 * 1024]
PRODUCTION_CENTERS = {"dal09", "fra02", "lon02", "syd01"}


def stream_json_array(handle: TextIO, *, read_size: int = 1024 * 1024) -> Iterator[dict[str, Any]]:
    """Yield objects from a JSON array without loading the complete file."""

    decoder = json.JSONDecoder()
    buffer = ""
    position = 0
    eof = False
    started = False
    expect_value = True

    def refill() -> None:
        nonlocal buffer, position, eof
        if position:
            buffer = buffer[position:]
            position = 0
        chunk = handle.read(read_size)
        if chunk:
            buffer += chunk
        else:
            eof = True

    while True:
        while position >= len(buffer) and not eof:
            refill()
        while position < len(buffer) and buffer[position].isspace():
            position += 1
        if position >= len(buffer):
            if eof:
                if started:
                    raise ValueError("truncated JSON array")
                return
            refill()
            continue
        if not started:
            if buffer[position] != "[":
                raise ValueError("trace file must contain a top-level JSON array")
            position += 1
            started = True
            continue
        while position < len(buffer) and buffer[position].isspace():
            position += 1
        if position >= len(buffer) and not eof:
            refill()
            continue
        if position < len(buffer) and buffer[position] == "]":
            position += 1
            return
        if not expect_value:
            if position < len(buffer) and buffer[position] == ",":
                position += 1
                expect_value = True
                continue
            if not eof:
                refill()
                continue
            raise ValueError("expected comma between JSON array elements")
        while True:
            try:
                value, end = decoder.raw_decode(buffer, position)
                break
            except json.JSONDecodeError:
                if eof:
                    raise
                refill()
        if not isinstance(value, dict):
            raise ValueError("trace array element is not an object")
        position = end
        expect_value = False
        yield value


def iter_trace_file(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        yield from stream_json_array(handle)


def merge_day_files(paths: list[Path]) -> Iterator[dict[str, Any]]:
    """Merge timestamp-sorted shard arrays for one data-center day."""

    iterators = [iter_trace_file(path) for path in sorted(paths)]
    heap: list[tuple[str, int, dict[str, Any], Iterator[dict[str, Any]]]] = []
    serial = 0
    for iterator in iterators:
        try:
            record = next(iterator)
        except StopIteration:
            continue
        heapq.heappush(heap, (str(record.get("timestamp", "")), serial, record, iterator))
        serial += 1
    while heap:
        _timestamp, _serial, record, iterator = heapq.heappop(heap)
        yield record
        try:
            following = next(iterator)
        except StopIteration:
            continue
        heapq.heappush(
            heap, (str(following.get("timestamp", "")), serial, following, iterator),
        )
        serial += 1


class LRUCache:
    __slots__ = ("budget", "entries", "resident_bytes")

    def __init__(self, budget: int):
        self.budget = int(budget)
        self.entries: OrderedDict[str, int] = OrderedDict()
        self.resident_bytes = 0

    def access(self, key: str, size: int) -> tuple[bool, int, int, int]:
        """Return hit, resident-byte delta, evicted objects, evicted bytes."""

        before = self.resident_bytes
        evicted_objects = 0
        evicted_bytes = 0
        if key in self.entries:
            hit = True
            previous_size = self.entries.pop(key)
            self.resident_bytes -= previous_size
        else:
            hit = False
        if size <= self.budget:
            self.entries[key] = size
            self.resident_bytes += size
            while self.resident_bytes > self.budget:
                _old_key, old_size = self.entries.popitem(last=False)
                self.resident_bytes -= old_size
                evicted_objects += 1
                evicted_bytes += old_size
        return hit, self.resident_bytes - before, evicted_objects, evicted_bytes


@dataclass
class BudgetMetrics:
    budget_bytes: int
    requests: int = 0
    request_hits: int = 0
    requested_bytes: int = 0
    byte_hits: int = 0
    objects_too_large: int = 0
    bytes_too_large: int = 0
    evicted_objects: int = 0
    evicted_bytes: int = 0
    resident_bytes: int = 0
    peak_resident_bytes: int = 0

    def record(
        self,
        *,
        hit: bool,
        size: int,
        delta: int,
        evicted_objects: int,
        evicted_bytes: int,
    ) -> None:
        self.requests += 1
        self.requested_bytes += size
        if hit:
            self.request_hits += 1
            self.byte_hits += size
        if size > self.budget_bytes:
            self.objects_too_large += 1
            self.bytes_too_large += size
        self.evicted_objects += evicted_objects
        self.evicted_bytes += evicted_bytes
        self.resident_bytes += delta
        self.peak_resident_bytes = max(self.peak_resident_bytes, self.resident_bytes)

    def result(self, deployment_class: str) -> dict[str, Any]:
        return {
            "deployment_class": deployment_class,
            "budget_bytes_per_client": self.budget_bytes,
            "budget_mib_per_client": round(self.budget_bytes / (1024 * 1024), 3),
            "successful_full_blob_get_requests": self.requests,
            "warm_request_hits": self.request_hits,
            "warm_request_hit_fraction": round(self.request_hits / self.requests, 6) if self.requests else 0.0,
            "successful_full_blob_get_bytes": self.requested_bytes,
            "warm_byte_hits": self.byte_hits,
            "warm_byte_hit_fraction": round(self.byte_hits / self.requested_bytes, 6) if self.requested_bytes else 0.0,
            "objects_larger_than_budget": self.objects_too_large,
            "bytes_in_objects_larger_than_budget": self.bytes_too_large,
            "evicted_objects": self.evicted_objects,
            "evicted_bytes": self.evicted_bytes,
            "resident_bytes_at_end_across_clients": self.resident_bytes,
            "peak_resident_bytes_across_clients": self.peak_resident_bytes,
        }


def trace_files_by_center_and_day(trace_root: Path) -> dict[str, dict[str, list[Path]]]:
    data_centers = trace_root / "data_centers" if (trace_root / "data_centers").is_dir() else trace_root
    grouped: dict[str, dict[str, list[Path]]] = {}
    for path in data_centers.rglob("*.json"):
        match = DATE_PATTERN.search(path.name)
        if match is None:
            continue
        center = path.parent.name
        grouped.setdefault(center, {}).setdefault(match.group(1), []).append(path)
    if not grouped:
        raise ValueError(f"no trace JSON files found under {trace_root}")
    return grouped


def normalize_blob_get(record: dict[str, Any]) -> tuple[str, str, int] | None:
    if str(record.get("http.request.method", "")).upper() != "GET":
        return None
    try:
        status = int(record.get("http.response.status", 0))
        size = int(record.get("http.response.written", 0))
    except (TypeError, ValueError):
        return None
    uri = str(record.get("http.request.uri", ""))
    client = str(record.get("http.request.remoteaddr", ""))
    if status != 200 or size <= 0 or not client or "/blobs/" not in f"/{uri}":
        return None
    return client, uri, size


def analyze_trace(
    *,
    trace_root: Path,
    budgets: list[int],
    max_records: int | None = None,
    progress_every: int = 1_000_000,
) -> dict[str, Any]:
    grouped = trace_files_by_center_and_day(trace_root)
    budget_metrics = {
        deployment_class: {budget: BudgetMetrics(budget) for budget in budgets}
        for deployment_class in ("all", "production", "nonproduction")
    }
    total_records = 0
    method_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    data_center_results = []
    stop = False
    for center, days in sorted(grouped.items()):
        deployment_class = "production" if center in PRODUCTION_CENTERS else "nonproduction"
        client_caches: dict[str, list[LRUCache]] = {}
        center_records = 0
        center_blob_gets = 0
        for day, paths in sorted(days.items()):
            for record in merge_day_files(paths):
                total_records += 1
                center_records += 1
                timestamp = str(record.get("timestamp", ""))
                if timestamp:
                    first_timestamp = timestamp if first_timestamp is None else min(first_timestamp, timestamp)
                    last_timestamp = timestamp if last_timestamp is None else max(last_timestamp, timestamp)
                method_counts[str(record.get("http.request.method", ""))] += 1
                status_counts[str(record.get("http.response.status", ""))] += 1
                normalized = normalize_blob_get(record)
                if normalized is not None:
                    center_blob_gets += 1
                    client, uri, size = normalized
                    caches = client_caches.get(client)
                    if caches is None:
                        caches = [LRUCache(budget) for budget in budgets]
                        client_caches[client] = caches
                    for budget, cache in zip(budgets, caches):
                        hit, delta, evicted_objects, evicted_bytes = cache.access(uri, size)
                        for metrics_class in ("all", deployment_class):
                            budget_metrics[metrics_class][budget].record(
                                hit=hit,
                                size=size,
                                delta=delta,
                                evicted_objects=evicted_objects,
                                evicted_bytes=evicted_bytes,
                            )
                if progress_every and total_records % progress_every == 0:
                    print(
                        f"processed_records={total_records} center={center} day={day}",
                        file=sys.stderr,
                        flush=True,
                    )
                if max_records is not None and total_records >= max_records:
                    stop = True
                    break
            if stop:
                break
        data_center_results.append({
            "data_center": center,
            "deployment_class": deployment_class,
            "days": len(days),
            "trace_files": sum(len(paths) for paths in days.values()),
            "records": center_records,
            "successful_full_blob_get_requests": center_blob_gets,
            "anonymized_clients": len(client_caches),
        })
        if stop:
            break
    return {
        "records_processed": total_records,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "method_counts": dict(sorted(method_counts.items())),
        "response_status_counts": dict(sorted(status_counts.items())),
        "data_centers": data_center_results,
        "budget_results": [
            budget_metrics[deployment_class][budget].result(deployment_class)
            for deployment_class in ("production", "nonproduction", "all")
            for budget in budgets
        ],
        "partial_max_records": max_records,
    }


def sha1_file(path: Path) -> str:
    hasher = hashlib.sha1()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--budget-mib", type=int, nargs="+", default=[64, 256, 1024])
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--progress-every", type=int, default=1_000_000)
    parser.add_argument(
        "--output-json", type=Path,
        default=ROOT / "results" / "ibm_registry_trace_residency_v3_17.json",
    )
    parser.add_argument(
        "--output-csv", type=Path,
        default=ROOT / "results" / "ibm_registry_trace_residency_v3_17.csv",
    )
    args = parser.parse_args()
    budgets = [value * 1024 * 1024 for value in args.budget_mib]
    if any(value <= 0 for value in budgets) or budgets != sorted(set(budgets)):
        raise SystemExit("budgets must be positive, unique, and sorted")
    archive_sha1 = None
    if args.archive is not None:
        archive_sha1 = sha1_file(args.archive)
        if archive_sha1 != EXPECTED_ARCHIVE_SHA1:
            raise SystemExit(f"trace archive SHA-1 mismatch: {archive_sha1}")
    analysis = analyze_trace(
        trace_root=args.trace_root,
        budgets=budgets,
        max_records=args.max_records,
        progress_every=args.progress_every,
    )
    result = {
        "experiment": "ibm_production_registry_trace_residency_v3_17",
        "claim_scope": (
            "same-client exact full-blob availability under byte-bounded LRU; an upper bound for "
            "authorized warm state because authorization changes and client-local deletions are not observed; "
            "not evidence of within-blob chunk alignment"
        ),
        "source": {
            "paper": SOURCE_PAPER_URL,
            "trace": SOURCE_TRACE_URL,
            "archive_name": "DockerRegistryTraces.tar.gz",
            "archive_sha1": archive_sha1 or EXPECTED_ARCHIVE_SHA1,
            "expected_archive_sha1": EXPECTED_ARCHIVE_SHA1,
        },
        "method": (
            "successful status-200 GET requests whose URI contains /blobs/ and whose response writes "
            "positive bytes; per-data-center anonymized client identity; daily logstash shards merged "
            "by ISO timestamp; exact object URI and observed response size; true per-client LRU; "
            "production centers are dal09, fra02, lon02, and syd01 as classified in the source paper"
        ),
        "provenance": {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(),
            "python": sys.version,
            "trace_root_not_part_of_submission": str(args.trace_root),
        },
        "analysis": analysis,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(analysis["budget_results"][0]), lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(analysis["budget_results"])
    print(json.dumps({
        "records_processed": analysis["records_processed"],
        "first_timestamp": analysis["first_timestamp"],
        "last_timestamp": analysis["last_timestamp"],
        "budget_results": analysis["budget_results"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
