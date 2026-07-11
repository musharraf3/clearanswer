"""Orchestration: math check → retrieve → model → groundedness guard.

Every step leaves an audit trail in the result JSON: math findings with
expected/actual numbers, retrieval scores with matched terms, citations with
verification status. Nothing the user sees is unexplainable.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from .corpus import chunk_index, load_corpus, load_plan
from .grounding import apply_guard
from .mathcheck import check_eob
from .models import DecodeResult, LineDecode, MathFinding, RetrievedChunk, Severity
from .retriever import BM25Index


def _line_query(line: dict) -> str:
    parts = [line.get("description", ""), line.get("cpt", ""), line.get("network", "")]
    parts += line.get("codes", [])
    parts += line.get("remark_codes", [])
    if line.get("place_of_service"):
        parts.append(line["place_of_service"])
    return " ".join(str(p) for p in parts)


def run_decode(eob: dict, arm: str) -> DecodeResult:
    from .agent import build_user_prompt, call_model  # lazy: needs anthropic only in live mode

    chunks = load_corpus()
    index = BM25Index(chunks)
    by_id = chunk_index(chunks)
    plan = load_plan()

    findings = check_eob(eob, plan)
    findings_json = json.dumps([asdict(f) for f in findings], indent=2, default=lambda o: o.value)

    retrieval: dict[str, list[RetrievedChunk]] = {}
    retrieved_for_prompt: dict[str, list[dict]] = {}
    for line in eob["lines"]:
        hits = index.search(_line_query(line), k=4)
        retrieval[line["line_id"]] = hits
        retrieved_for_prompt[line["line_id"]] = [
            {"chunk_id": h.chunk_id, "score": h.score,
             "title": by_id[h.chunk_id].title, "text": by_id[h.chunk_id].text}
            for h in hits
        ]

    raw, usage, model = call_model(arm, build_user_prompt(eob, findings_json, retrieved_for_prompt))

    lines = [LineDecode.from_dict(l) for l in raw["lines"]]
    for l in lines:
        l.retrieval = retrieval.get(l.line_id, [])

    has_error_finding = any(f.severity == Severity.ERROR for f in findings)
    result = DecodeResult(
        eob_id=eob["eob_id"], model=model, arm=arm, mode="live",
        summary=raw["summary"], total_you_owe=raw.get("total_you_owe"),
        lines=lines, math_findings=findings,
        actions=list(raw.get("actions", [])),
        escalate=bool(raw.get("escalate", False)) or has_error_finding,
        escalate_reason=raw.get("escalate_reason") or (
            "Code-level checks found possible billing errors — a human should confirm "
            "before anything is paid." if has_error_finding else None),
        usage=usage,
    )
    return apply_guard(result, by_id)
