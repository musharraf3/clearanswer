"""Offline demo mode: replays outputs from REAL API runs (bundled in
examples/outputs/), so the demo needs no key — while the groundedness guard
and math checker still execute live in Python on your machine, every time."""

from __future__ import annotations

import json
from pathlib import Path

from .corpus import chunk_index, load_corpus
from .grounding import apply_guard
from .models import DecodeResult

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "examples" / "outputs"


def run_offline(eob: dict, arm: str = "worker+skill") -> DecodeResult:
    path = OUTPUT_DIR / f"{eob['eob_id']}__{arm.replace('+', '_')}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No cached output for {eob['eob_id']} / arm '{arm}'. "
            f"Set ANTHROPIC_API_KEY for live mode, or use a bundled example.")
    result = DecodeResult.from_dict(json.loads(path.read_text(encoding="utf-8")))
    result.mode = "offline-cache"
    return apply_guard(result, chunk_index(load_corpus()))
