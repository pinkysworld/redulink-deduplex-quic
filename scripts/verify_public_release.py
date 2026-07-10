#!/usr/bin/env python3
"""Verify the public GitHub state for a ReduLink release.

This checker intentionally uses unauthenticated GitHub API and raw-content
requests so artifact reviewers can distinguish real repository state from stale
HTML or CDN views.
"""

from __future__ import annotations

import argparse
import json
import time
from urllib.request import Request, urlopen


DEFAULT_REPO = "pinkysworld/redulink-deduplex-quic"


def fetch(url: str) -> bytes:
    req = Request(
        url,
        headers={
            "User-Agent": "redulink-public-release-check",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urlopen(req, timeout=30) as response:
        return response.read()


def fetch_json(url: str) -> dict:
    return json.loads(fetch(url).decode("utf-8"))


def ok(name: str, condition: bool) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {name}")
    print(f"OK: {name}")


def raw_url(repo: str, ref: str, path: str, cachebust: bool = False) -> str:
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
    if cachebust:
        url += f"?cachebust={int(time.time())}"
    return url


def text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def check_text_blob(name: str, data: bytes, needles: list[str]) -> None:
    body = text(data)
    ok(f"{name} is LF-only", b"\r" not in data)
    for needle in needles:
        ok(f"{name} contains {needle}", needle in body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--version", default="3.14")
    args = parser.parse_args()

    tag = f"v{args.version}-journal-submission"
    stem = f"ReduLink_journal_ready_v{args.version.replace('.', '_')}"
    builder = f"scripts/build_manuscript_v{args.version.replace('.', '_')}.py"
    response_matrix = f"REVIEWER_RESPONSE_v{args.version.replace('.', '_')}.md"
    api_base = f"https://api.github.com/repos/{args.repo}"

    latest = fetch_json(f"{api_base}/releases/latest")
    ok("latest release tag", latest["tag_name"] == tag)

    release = fetch_json(f"{api_base}/releases/tags/{tag}")
    assets = {asset["name"] for asset in release["assets"]}
    expected_assets = {
        "Dockerfile",
        "MANUSCRIPT_SHA256.txt",
        "PUBLIC_REVIEWER_CHECKLIST.md",
        response_matrix,
        "requirements-lock.txt",
        f"{stem}.docx",
        f"{stem}.pdf",
        "verify_public_release.py",
    }
    ok("release assets complete", expected_assets <= assets)

    main_commit = fetch_json(f"{api_base}/commits/main")["sha"]
    print(f"main_sha: {main_commit}")

    common = [
        ("README.md", [tag, f"{stem}.pdf", "scripts/verify_public_release.py"]),
        ("CITATION.cff", [f'version: "{args.version}"']),
        ("SOURCE_COMMIT.txt", [tag]),
        ("SOURCE_GIT_STATUS.txt", [f"v{args.version}"]),
        ("MANUSCRIPT_SHA256.txt", [f"{stem}.docx", f"{stem}.pdf"]),
        ("pyproject.toml", [f'version = "{args.version}"', f'artifact_tag = "{tag}"']),
        ("PUBLIC_REVIEWER_CHECKLIST.md", [tag, f"{stem}.pdf"]),
        (response_matrix, [f"v{args.version}", "Reviewer Response Matrix"]),
        (builder, [f"{stem}.docx", "Repeated native QUIC trials (n = 20)"]),
    ]
    for ref, cachebust in [("main", True), (tag, False), (main_commit, False)]:
        for path, needles in common:
            data = fetch(raw_url(args.repo, ref, path, cachebust=cachebust))
            check_text_blob(f"{ref}:{path}", data, needles)

    print(f"public release verification OK: {tag}")


if __name__ == "__main__":
    main()
