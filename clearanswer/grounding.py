"""Groundedness guard v2.

Stricter than FirstPass v1: each citation names a specific chunk_id, and the
quote must appear verbatim (normalized) in THAT chunk — not merely anywhere in
the corpus. Pure Python, runs in every mode, flags failures for human review.
"""

from __future__ import annotations

import difflib
import re

from .corpus import Chunk
from .models import DecodeResult, GroundednessReport

FUZZY = 0.85


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", re.sub(r"\s+", " ", t.lower())).strip()


def _in_chunk(quote: str, chunk_text: str) -> bool:
    q, h = _norm(quote), _norm(chunk_text)
    if not q:
        return False
    if q in h:
        return True
    hw, qw = h.split(), q.split()
    win = len(qw)
    for i in range(0, max(1, len(hw) - win + 1)):
        if difflib.SequenceMatcher(None, q, " ".join(hw[i:i + win])).ratio() >= FUZZY:
            return True
    return False


def apply_guard(result: DecodeResult, index: dict[str, Chunk]) -> DecodeResult:
    total = ok = 0
    bad: list[str] = []
    for line in result.lines:
        for cit in line.citations:
            total += 1
            chunk = index.get(cit.chunk_id)
            verified = bool(chunk) and _in_chunk(cit.quote, f"{chunk.title}. {chunk.text}")
            cit.verified = verified
            if verified:
                ok += 1
            else:
                reason = "unknown chunk" if not chunk else "quote not found in cited chunk"
                bad.append(f"[{line.line_id} → {cit.chunk_id}] ({reason}) “{cit.quote}”")
    result.groundedness = GroundednessReport(total_quotes=total, verified_quotes=ok, unverified=bad)
    if total and ok / total < 0.8 and not result.escalate:
        result.escalate = True
        result.escalate_reason = (
            "Groundedness below threshold — too many statements could not be verified "
            "against the source documents. Route to a human reviewer.")
    return result
