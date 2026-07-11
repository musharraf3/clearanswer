"""Corpus loader. Three sources, all bundled and human-readable:

  data/codes/carc_rarc.json  — claim adjustment code dictionary (public X12/CMS codes,
                               plain-language entries written for this project)
  data/plan/sbc_sunrise.json — synthetic plan benefits document ("Sunrise Health PPO")
  data/rights/rights.json    — patient rights: appeals, No Surprises Act, itemized bills

Every chunk has a stable ID so answers can cite exactly where they came from.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


@dataclass
class Chunk:
    chunk_id: str
    source: str   # "codes" | "plan" | "rights"
    title: str
    text: str


def load_corpus() -> list[Chunk]:
    chunks: list[Chunk] = []
    for source, path in [
        ("codes", DATA / "codes" / "carc_rarc.json"),
        ("plan", DATA / "plan" / "sbc_sunrise.json"),
        ("rights", DATA / "rights" / "rights.json"),
    ]:
        for item in json.loads(path.read_text(encoding="utf-8"))["chunks"]:
            chunks.append(Chunk(chunk_id=item["id"], source=source,
                                title=item["title"], text=item["text"]))
    return chunks


def load_plan() -> dict:
    """Structured plan facts used by the deterministic math checker."""
    return json.loads((DATA / "plan" / "sbc_sunrise.json").read_text(encoding="utf-8"))["facts"]


def chunk_index(chunks: list[Chunk]) -> dict[str, Chunk]:
    return {c.chunk_id: c for c in chunks}
