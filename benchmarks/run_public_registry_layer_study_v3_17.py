#!/usr/bin/env python3
"""Analyze exact chunk reuse in pinned public OCI/Docker registry layer bytes.

The runner resolves no mutable tags during measurement. A committed manifest
pins each linux/amd64 platform manifest digest. It downloads compressed layer
blobs through the Docker Registry HTTP API, verifies every digest and declared
size, removes layers already reusable by whole-layer content addressing, and
then measures fixed-size ReduLink chunk reuse only within the remaining changed
blob bytes. This separates ordinary registry CAS reuse from incremental
within-blob reuse.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Iterable
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import redulink_secure as secure  # type: ignore  # noqa: E402
import redulink_wire as wire  # type: ignore  # noqa: E402

REGISTRY = "https://registry-1.docker.io"
TOKEN_ENDPOINT = "https://auth.docker.io/token"
USER_AGENT = "ReduLink-research-artifact/3.17"
MANIFEST_ACCEPT = ", ".join([
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])
WIRE_SCOPE = "registry-layer-study"


def registry_token(repository: str) -> str:
    query = urllib.parse.urlencode({
        "service": "registry.docker.io",
        "scope": f"repository:{repository}:pull",
    })
    request = urllib.request.Request(
        f"{TOKEN_ENDPOINT}?{query}", headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return str(json.load(response)["token"])


def authenticated_request(url: str, token: str, *, accept: str | None = None) -> urllib.request.Request:
    headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
    if accept is not None:
        headers["Accept"] = accept
    return urllib.request.Request(url, headers=headers)


def fetch_manifest(repository: str, digest: str, token: str) -> dict[str, Any]:
    url = f"{REGISTRY}/v2/{repository}/manifests/{digest}"
    with urllib.request.urlopen(
        authenticated_request(url, token, accept=MANIFEST_ACCEPT), timeout=120,
    ) as response:
        raw = response.read()
        content_digest = response.headers.get("Docker-Content-Digest", "")
        content_type = response.headers.get("Content-Type", "")
    actual_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if actual_digest != digest or content_digest != digest:
        raise RuntimeError(
            f"manifest digest mismatch for {repository}: expected {digest}, "
            f"body {actual_digest}, header {content_digest}",
        )
    manifest = json.loads(raw)
    if "layers" not in manifest:
        raise RuntimeError(f"pinned digest {digest} is not an image manifest")
    return {
        "repository": repository,
        "digest": digest,
        "content_type": content_type,
        "raw_bytes": len(raw),
        "config": manifest.get("config", {}),
        "layers": manifest["layers"],
    }


def blob_path(cache: Path, repository: str, digest: str) -> Path:
    return cache / repository.replace("/", "_") / digest.replace(":", "_")


def verify_blob(path: Path, *, digest: str, size: int) -> None:
    if path.stat().st_size != size:
        raise RuntimeError(f"blob size mismatch for {digest}: {path.stat().st_size} != {size}")
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    actual = "sha256:" + hasher.hexdigest()
    if actual != digest:
        raise RuntimeError(f"blob digest mismatch: {actual} != {digest}")


def fetch_blob(
    *,
    cache: Path,
    repository: str,
    descriptor: dict[str, Any],
    token: str,
) -> Path:
    digest = str(descriptor["digest"])
    size = int(descriptor["size"])
    destination = blob_path(cache, repository, digest)
    if destination.exists():
        verify_blob(destination, digest=digest, size=size)
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".part")
    request = authenticated_request(
        f"{REGISTRY}/v2/{repository}/blobs/{digest}", token,
    )
    hasher = hashlib.sha256()
    written = 0
    try:
        with urllib.request.urlopen(request, timeout=300) as response, temporary.open("wb") as handle:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                handle.write(block)
                hasher.update(block)
                written += len(block)
        actual = "sha256:" + hasher.hexdigest()
        if written != size or actual != digest:
            raise RuntimeError(
                f"downloaded blob verification failed for {digest}: "
                f"size {written}/{size}, digest {actual}",
            )
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def iter_chunks(path: Path, chunk_size: int) -> Iterable[bytes]:
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                return
            yield chunk


def chunk_key(chunk: bytes) -> bytes:
    return len(chunk).to_bytes(4, "big") + hashlib.sha256(chunk).digest()


def build_chunk_dictionary(paths: Iterable[Path], chunk_size: int) -> dict[bytes, bytes]:
    dictionary: dict[bytes, bytes] = {}
    for path in paths:
        for chunk in iter_chunks(path, chunk_size):
            dictionary.setdefault(chunk_key(chunk), chunk)
    return dictionary


def measured_frame_overheads(chunk_size: int) -> tuple[int, int]:
    frames, _ = secure.encode(
        b"A" * chunk_size,
        secret=b"registry-layer-overhead-probe",
        epoch=7,
        scope=WIRE_SCOPE,
        stream_id=0,
        chunker="fixed",
        chunk_size=chunk_size,
    )
    full = frames[0]
    ref = dataclasses.replace(full, kind="REF", payload=b"")
    full_overhead = len(wire.encode_message({"t": "FRAME", "seq": 0, "frame": full})) - len(full.payload)
    ref_overhead = len(wire.encode_message({"t": "FRAME", "seq": 1, "frame": ref}))
    return full_overhead, ref_overhead


def analyze_changed_blobs(
    *,
    warm_paths: list[Path],
    update_descriptors_and_paths: list[tuple[dict[str, Any], Path]],
    chunk_size: int,
    full_overhead: int,
    ref_overhead: int,
) -> dict[str, Any]:
    dictionary = build_chunk_dictionary(warm_paths, chunk_size)
    full_frames = 0
    ref_frames = 0
    matched_bytes = 0
    changed_bytes = 0
    wire_bytes = 0
    reconstruction_ok = True
    for descriptor, path in update_descriptors_and_paths:
        reconstructed = hashlib.sha256()
        expected_digest = str(descriptor["digest"])
        for chunk in iter_chunks(path, chunk_size):
            changed_bytes += len(chunk)
            known = dictionary.get(chunk_key(chunk))
            if known is not None:
                if known != chunk:
                    raise RuntimeError("SHA-256 chunk-key collision")
                ref_frames += 1
                matched_bytes += len(chunk)
                wire_bytes += ref_overhead
                reconstructed.update(known)
            else:
                full_frames += 1
                wire_bytes += full_overhead + len(chunk)
                reconstructed.update(chunk)
        reconstruction_ok &= "sha256:" + reconstructed.hexdigest() == expected_digest
    return {
        "warm_dictionary_unique_chunks": len(dictionary),
        "changed_layer_bytes": changed_bytes,
        "matched_chunk_bytes_within_changed_layers": matched_bytes,
        "matched_chunk_byte_fraction_within_changed_layers": round(
            matched_bytes / changed_bytes, 6,
        ) if changed_bytes else 0.0,
        "full_frames": full_frames,
        "ref_frames": ref_frames,
        "redulink_wire_bytes_for_changed_layers": wire_bytes,
        "redulink_multiplier_vs_whole_layer_cas_changed_bytes": round(
            changed_bytes / wire_bytes, 6,
        ) if wire_bytes else 0.0,
        "reconstruction_ok": reconstruction_ok,
    }


def analyze_pair(
    *,
    row: dict[str, str],
    cache: Path,
    chunk_size: int,
    full_overhead: int,
    ref_overhead: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    repository = row["repository"]
    token = registry_token(repository)
    warm_manifest = fetch_manifest(repository, row["warm_manifest_digest"], token)
    update_manifest = fetch_manifest(repository, row["update_manifest_digest"], token)
    warm_descriptors = list(warm_manifest["layers"])
    update_descriptors = list(update_manifest["layers"])
    warm_paths = [
        fetch_blob(cache=cache, repository=repository, descriptor=descriptor, token=token)
        for descriptor in warm_descriptors
    ]
    update_paths = [
        fetch_blob(cache=cache, repository=repository, descriptor=descriptor, token=token)
        for descriptor in update_descriptors
    ]
    warm_digests = {str(descriptor["digest"]) for descriptor in warm_descriptors}
    unchanged = [
        descriptor for descriptor in update_descriptors
        if str(descriptor["digest"]) in warm_digests
    ]
    changed = [
        (descriptor, path)
        for descriptor, path in zip(update_descriptors, update_paths)
        if str(descriptor["digest"]) not in warm_digests
    ]
    update_bytes = sum(int(descriptor["size"]) for descriptor in update_descriptors)
    unchanged_bytes = sum(int(descriptor["size"]) for descriptor in unchanged)
    analysis = analyze_changed_blobs(
        warm_paths=warm_paths,
        update_descriptors_and_paths=changed,
        chunk_size=chunk_size,
        full_overhead=full_overhead,
        ref_overhead=ref_overhead,
    )
    analysis.update({
        "label": row["label"],
        "repository": repository,
        "warm_tag_provenance_only": row["warm_tag"],
        "warm_index_digest": row["warm_index_digest"],
        "warm_manifest_digest": row["warm_manifest_digest"],
        "update_tag_provenance_only": row["update_tag"],
        "update_index_digest": row["update_index_digest"],
        "update_manifest_digest": row["update_manifest_digest"],
        "platform": f"{row['platform_os']}/{row['platform_architecture']}",
        "warm_layer_count": len(warm_descriptors),
        "update_layer_count": len(update_descriptors),
        "update_layer_bytes": update_bytes,
        "whole_layer_cas_hit_count": len(unchanged),
        "whole_layer_cas_hit_bytes": unchanged_bytes,
        "whole_layer_cas_hit_byte_fraction": round(unchanged_bytes / update_bytes, 6),
        "whole_layer_cas_changed_bytes": update_bytes - unchanged_bytes,
        "combined_cas_plus_redulink_total_update_multiplier": round(
            update_bytes / int(analysis["redulink_wire_bytes_for_changed_layers"]), 6,
        ) if analysis["redulink_wire_bytes_for_changed_layers"] else 0.0,
        "chunk_size_bytes": chunk_size,
        "full_frame_overhead_bytes": full_overhead,
        "ref_frame_bytes": ref_overhead,
        "manifest_and_http_overhead_excluded": True,
    })
    metadata = {
        "label": row["label"],
        "warm_manifest": warm_manifest,
        "update_manifest": update_manifest,
    }
    return analysis, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path,
        default=ROOT / "benchmarks" / "public_registry_layer_manifest_v3_17.csv",
    )
    parser.add_argument(
        "--cache", type=Path, default=Path("/tmp/redulink-public-registry-layer-cache-v3-17"),
    )
    parser.add_argument("--chunk-size", type=int, default=4096)
    parser.add_argument(
        "--output-json", type=Path,
        default=ROOT / "results" / "public_registry_layer_study_v3_17.json",
    )
    parser.add_argument(
        "--output-csv", type=Path,
        default=ROOT / "results" / "public_registry_layer_study_v3_17.csv",
    )
    args = parser.parse_args()
    if args.chunk_size < 512:
        raise SystemExit("chunk size must be at least 512 bytes")
    full_overhead, ref_overhead = measured_frame_overheads(args.chunk_size)
    rows = []
    manifests = []
    with args.manifest.open(newline="", encoding="utf-8") as handle:
        for manifest_row in csv.DictReader(handle):
            analysis, metadata = analyze_pair(
                row=manifest_row,
                cache=args.cache,
                chunk_size=args.chunk_size,
                full_overhead=full_overhead,
                ref_overhead=ref_overhead,
            )
            rows.append(analysis)
            manifests.append(metadata)
    aggregate_update = sum(int(row["update_layer_bytes"]) for row in rows)
    aggregate_changed = sum(int(row["whole_layer_cas_changed_bytes"]) for row in rows)
    aggregate_matched = sum(int(row["matched_chunk_bytes_within_changed_layers"]) for row in rows)
    aggregate_wire = sum(int(row["redulink_wire_bytes_for_changed_layers"]) for row in rows)
    result = {
        "experiment": "pinned_public_registry_layer_study_v3_17",
        "scope": (
            "compressed linux/amd64 registry layer blobs pinned by platform-manifest digest; "
            "whole-layer CAS hits removed before fixed-chunk ReduLink analysis"
        ),
        "registry_api": "Docker Registry HTTP API V2",
        "registry": REGISTRY,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "platform": platform.platform(),
            "python": sys.version,
            "manifest": str(args.manifest.relative_to(ROOT)),
            "cache_not_part_of_submission": str(args.cache),
        },
        "parameters": {
            "chunker": "fixed per blob",
            "chunk_size_bytes": args.chunk_size,
            "wire_scope": WIRE_SCOPE,
            "full_frame_overhead_bytes": full_overhead,
            "ref_frame_bytes": ref_overhead,
        },
        "aggregate": {
            "pairs": len(rows),
            "update_layer_bytes": aggregate_update,
            "whole_layer_cas_changed_bytes": aggregate_changed,
            "whole_layer_cas_hit_byte_fraction": round(
                (aggregate_update - aggregate_changed) / aggregate_update, 6,
            ),
            "matched_chunk_bytes_within_changed_layers": aggregate_matched,
            "matched_chunk_byte_fraction_within_changed_layers": round(
                aggregate_matched / aggregate_changed, 6,
            ) if aggregate_changed else 0.0,
            "redulink_wire_bytes_for_changed_layers": aggregate_wire,
            "redulink_multiplier_vs_whole_layer_cas_changed_bytes": round(
                aggregate_changed / aggregate_wire, 6,
            ) if aggregate_wire else 0.0,
            "combined_cas_plus_redulink_total_update_multiplier": round(
                aggregate_update / aggregate_wire, 6,
            ) if aggregate_wire else 0.0,
            "all_reconstructed": all(bool(row["reconstruction_ok"]) for row in rows),
        },
        "rows": rows,
        "pinned_manifests": manifests,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(result["aggregate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
