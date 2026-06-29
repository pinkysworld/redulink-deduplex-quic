#!/usr/bin/env python3
"""Check manuscript reference numbering and visible in-text citation coverage."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[1]

_submission = ROOT / "paper/submission"
_journal_candidates = sorted(_submission.glob("ReduLink_journal_ready_v*.docx"))
_systems_candidates = sorted(_submission.glob("ReduLink_systems_ready_v*.docx"))
DOCX = (
    _journal_candidates[-1]
    if _journal_candidates
    else (_systems_candidates[-1] if _systems_candidates else _submission / "ReduLink_journal_ready_v2_5.docx")
)


def expand_token(token: str) -> set[int]:
    values: set[int] = set()
    for part in token.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = [int(x.strip()) for x in part.split('-', 1)]
            values.update(range(a, b + 1))
        else:
            values.add(int(part))
    return values


def main() -> int:
    text = "\n".join(p.text for p in Document(DOCX).paragraphs)
    if "References" not in text:
        print("missing References heading", file=sys.stderr)
        return 1
    before_refs, refs = text.split("References", 1)
    ref_nums = {int(x) for x in re.findall(r"^\[(\d+)\]", refs, flags=re.MULTILINE)}
    cited: set[int] = set()
    for token in re.findall(r"\[([0-9,\- ]+)\]", before_refs):
        cited.update(expand_token(token))
    missing = sorted(ref_nums - cited)
    dangling = sorted(cited - ref_nums)
    if missing or dangling:
        print(f"missing in-text citations for refs: {missing}", file=sys.stderr)
        print(f"dangling in-text citation numbers: {dangling}", file=sys.stderr)
        return 1
    print(f"citation check OK: {len(ref_nums)} references, {len(cited)} cited in manuscript body")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
