"""Three-arm eval harness for ClearAnswer.

Arms:
  worker         Haiku 4.5, no skill pack (baseline)
  worker+skill   Haiku 4.5 + Fable-5-authored skill pack (the product config)
  teacher+skill  Fable 5 + skill pack (quality ceiling)

Metrics per arm:
  * line category accuracy vs gold (accept-lists)
  * must-mention coverage (key concepts present in member-facing text)
  * citation groundedness (verbatim quotes verified in cited chunks, in code)
  * escalation accuracy (escalates exactly when it should)
  * reading grade level (Flesch-Kincaid, computed in code; target <= 9)
  * real token usage and real dollar cost from the API responses

Usage:
  python evals/run_evals.py                  # run all arms live (needs ANTHROPIC_API_KEY)
  python evals/run_evals.py --skip-cached    # reuse cached outputs where present
  python evals/run_evals.py --arms worker+skill

Every live result is cached to examples/outputs/ so the offline demo replays
REAL model outputs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clearanswer.corpus import chunk_index, load_corpus  # noqa: E402
from clearanswer.grounding import apply_guard  # noqa: E402
from clearanswer.models import DecodeResult  # noqa: E402

EOBS = ROOT / "examples" / "eobs"
OUT = ROOT / "examples" / "outputs"
GOLD = json.loads((ROOT / "evals" / "gold.json").read_text(encoding="utf-8"))
ARMS = ["worker", "worker+skill", "teacher+skill"]

# $/1M tokens (input, output) — Anthropic list prices, July 2026
PRICE = {"claude-haiku-4-5-20251001": (1.0, 5.0), "claude-fable-5": (10.0, 50.0)}


def fk_grade(text: str) -> float:
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    words = re.findall(r"[a-zA-Z]+", text)
    if not words:
        return 0.0
    def syl(w: str) -> int:
        w = w.lower()
        groups = len(re.findall(r"[aeiouy]+", w))
        if w.endswith("e") and groups > 1:
            groups -= 1
        return max(1, groups)
    syllables = sum(syl(w) for w in words)
    return 0.39 * (len(words) / sentences) + 11.8 * (syllables / len(words)) - 15.59


def member_text(r: DecodeResult) -> str:
    return " ".join([r.summary] + [l.explanation for l in r.lines] + r.actions)


def score_case(r: DecodeResult, gold: dict) -> dict:
    cat_ok = cat_n = 0
    for l in r.lines:
        accept = gold["lines"].get(l.line_id)
        if accept is None:
            continue
        cat_n += 1
        cat_ok += l.category.value in accept

    text = member_text(r).lower()
    mm_ok = sum(any(v.lower() in text for v in variants) for variants in gold["must_mention"])
    mm_n = len(gold["must_mention"])

    found_flags = {f.check for f in r.math_findings}
    flags_ok = all(f in found_flags for f in gold["expected_flags"])

    g = r.groundedness
    return {
        "cat_ok": cat_ok, "cat_n": cat_n, "mm_ok": mm_ok, "mm_n": mm_n,
        "flags_ok": flags_ok, "esc_ok": r.escalate == gold["expected_escalate"],
        "quotes_ok": g.verified_quotes, "quotes_n": g.total_quotes,
        "fk": fk_grade(member_text(r)),
        "in_tok": (r.usage or {}).get("input_tokens", 0),
        "out_tok": (r.usage or {}).get("output_tokens", 0),
        "model": r.model,
    }


def get_result(eob: dict, arm: str, skip_cached: bool) -> DecodeResult:
    cache = OUT / f"{eob['eob_id']}__{arm.replace('+', '_')}.json"
    if skip_cached and cache.exists():
        r = DecodeResult.from_dict(json.loads(cache.read_text(encoding="utf-8")))
        return apply_guard(r, chunk_index(load_corpus()))
    from clearanswer.pipeline import run_decode
    r = run_decode(eob, arm)
    OUT.mkdir(parents=True, exist_ok=True)
    cache.write_text(r.to_json(), encoding="utf-8")
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--skip-cached", action="store_true")
    args = ap.parse_args()
    arms = [a.strip() for a in args.arms.split(",")]

    cases = sorted(EOBS.glob("*.json"))
    table_rows, arm_summaries = [], {}

    for arm in arms:
        agg = {k: 0 for k in ["cat_ok", "cat_n", "mm_ok", "mm_n", "esc_ok", "flagsok",
                              "quotes_ok", "quotes_n", "in_tok", "out_tok"]}
        fks, model_id = [], "?"
        for path in cases:
            eob = json.loads(path.read_text(encoding="utf-8"))
            r = get_result(eob, arm, args.skip_cached)
            s = score_case(r, GOLD[eob["eob_id"]])
            model_id = s["model"]
            for k in ["cat_ok", "cat_n", "mm_ok", "mm_n", "quotes_ok", "quotes_n",
                      "in_tok", "out_tok"]:
                agg[k] += s[k]
            agg["esc_ok"] += s["esc_ok"]
            agg["flagsok"] += s["flags_ok"]
            fks.append(s["fk"])
            print(f"{arm:14s} {eob['eob_id']}: cat {s['cat_ok']}/{s['cat_n']} "
                  f"mention {s['mm_ok']}/{s['mm_n']} grounded {s['quotes_ok']}/{s['quotes_n']} "
                  f"esc {'OK' if s['esc_ok'] else 'MISS'} fk {s['fk']:.1f}")

        pin, pout = PRICE.get(model_id, (0, 0))
        cost = agg["in_tok"] / 1e6 * pin + agg["out_tok"] / 1e6 * pout
        n = len(cases)
        arm_summaries[arm] = {
            "model": model_id,
            "cat": f"{agg['cat_ok']}/{agg['cat_n']} ({agg['cat_ok']/max(1,agg['cat_n']):.0%})",
            "mm": f"{agg['mm_ok']}/{agg['mm_n']} ({agg['mm_ok']/max(1,agg['mm_n']):.0%})",
            "ground": f"{agg['quotes_ok']}/{agg['quotes_n']} ({agg['quotes_ok']/max(1,agg['quotes_n']):.0%})",
            "esc": f"{agg['esc_ok']}/{n}",
            "fk": f"{sum(fks)/len(fks):.1f}",
            "tokens": f"{agg['in_tok']:,} in / {agg['out_tok']:,} out",
            "cost": f"${cost:.4f}",
        }
        table_rows.append(
            f"| {arm} | {model_id} | {arm_summaries[arm]['cat']} | {arm_summaries[arm]['mm']} "
            f"| {arm_summaries[arm]['ground']} | {arm_summaries[arm]['esc']} "
            f"| {arm_summaries[arm]['fk']} | {arm_summaries[arm]['cost']} |")
        print(f"== {arm}: {arm_summaries[arm]}\n")

    md = f"""# ClearAnswer eval results

Generated {date.today().isoformat()} · {len(cases)} synthetic EOB cases · all numbers from REAL API runs
(cached in `examples/outputs/`; math-flag detection is deterministic code and identical across arms).

| Arm | Model | Line category acc. | Must-mention coverage | Citation groundedness | Escalation acc. | FK grade | Total cost |
|---|---|---|---|---|---|---|---|
{chr(10).join(table_rows)}

**Reading the table:** "worker" is Haiku 4.5 alone; "worker+skill" adds the skill pack
authored by Claude Fable 5 (`skills/eob-decoding.md`); "teacher+skill" is Fable 5 itself,
as the quality ceiling. The product bet: worker+skill ≈ teacher quality at ~10x lower cost.
Prices: Haiku 4.5 $1/$5 per 1M tokens; Fable 5 $10/$50 per 1M tokens (list, July 2026).
"""
    (ROOT / "evals" / "results.md").write_text(md, encoding="utf-8")
    print("Wrote evals/results.md")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        # A missing API key is a setup step, not a crash. The agent already
        # writes a sentence for this case; print it rather than bury it under
        # a traceback the reader cannot act on.
        print(file=sys.stderr)
        print(exc, file=sys.stderr)
        print(file=sys.stderr)
        sys.exit(2)
