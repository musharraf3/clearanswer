"""Typed schemas. Stdlib-only (dataclasses) so the offline demo needs no installs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class LineCategory(str, Enum):
    PAID_IN_FULL = "paid_in_full"
    PREVENTIVE = "preventive"
    DEDUCTIBLE = "deductible"
    COINSURANCE = "coinsurance"
    COPAY = "copay"
    DENIAL_NOT_COVERED = "denial_not_covered"
    BUNDLED = "bundled"
    TIMELY_FILING_WRITEOFF = "timely_filing_writeoff"
    NSA_PROTECTED = "nsa_protected"
    COB_OTHER_PAYER = "cob_other_payer"
    POSSIBLE_ERROR = "possible_error"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class MathFinding:
    """Produced by deterministic code, never by the model."""

    line_id: Optional[str]  # None = EOB-level finding
    check: str              # e.g. "line_arithmetic", "duplicate_line", "oop_max"
    severity: Severity
    detail: str
    expected: Optional[float] = None
    actual: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MathFinding":
        return cls(line_id=d.get("line_id"), check=d["check"],
                   severity=Severity(d["severity"]), detail=d["detail"],
                   expected=d.get("expected"), actual=d.get("actual"))


@dataclass
class RetrievedChunk:
    chunk_id: str
    score: float
    matched_terms: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RetrievedChunk":
        return cls(chunk_id=d["chunk_id"], score=d["score"],
                   matched_terms=list(d.get("matched_terms", [])))


@dataclass
class Citation:
    chunk_id: str
    quote: str
    verified: Optional[bool] = None  # set by groundedness guard, in code

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Citation":
        return cls(chunk_id=d["chunk_id"], quote=d["quote"], verified=d.get("verified"))


@dataclass
class LineDecode:
    line_id: str
    category: LineCategory
    explanation: str                 # plain language, 8th-grade target
    you_owe: Optional[float]
    citations: list[Citation] = field(default_factory=list)
    retrieval: list[RetrievedChunk] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LineDecode":
        return cls(
            line_id=d["line_id"], category=LineCategory(d["category"]),
            explanation=d["explanation"], you_owe=d.get("you_owe"),
            citations=[Citation.from_dict(c) for c in d.get("citations", [])],
            retrieval=[RetrievedChunk.from_dict(r) for r in d.get("retrieval", [])],
        )


@dataclass
class GroundednessReport:
    total_quotes: int
    verified_quotes: int
    unverified: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.verified_quotes / self.total_quotes if self.total_quotes else 1.0


@dataclass
class DecodeResult:
    eob_id: str
    model: str
    arm: str                          # "worker" | "worker+skill" | "teacher+skill"
    mode: str                         # "live" | "offline-cache"
    summary: str
    total_you_owe: Optional[float]
    lines: list[LineDecode]
    math_findings: list[MathFinding]  # injected by code, shown to model AND user
    actions: list[str]                # concrete next steps for the member
    escalate: bool                    # True => route to a human
    escalate_reason: Optional[str] = None
    groundedness: Optional[GroundednessReport] = None
    usage: Optional[dict] = None      # real token counts from the API

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DecodeResult":
        g = d.get("groundedness")
        return cls(
            eob_id=d["eob_id"], model=d["model"], arm=d["arm"], mode=d["mode"],
            summary=d["summary"], total_you_owe=d.get("total_you_owe"),
            lines=[LineDecode.from_dict(x) for x in d["lines"]],
            math_findings=[MathFinding.from_dict(m) for m in d.get("math_findings", [])],
            actions=list(d.get("actions", [])), escalate=d.get("escalate", False),
            escalate_reason=d.get("escalate_reason"),
            groundedness=GroundednessReport(**g) if g else None,
            usage=d.get("usage"),
        )

    def to_json(self, indent: int = 2) -> str:
        def enc(o: Any) -> Any:
            if isinstance(o, Enum):
                return o.value
            raise TypeError(str(type(o)))
        return json.dumps(asdict(self), indent=indent, default=enc)
