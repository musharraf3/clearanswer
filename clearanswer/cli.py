"""CLI.

  python -m clearanswer decode --eob examples/eobs/eob_04.json [--arm worker+skill] [--offline]
  python -m clearanswer list-eobs
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .corpus import chunk_index, load_corpus
from .models import DecodeResult, Severity

EOB_DIR = Path(__file__).resolve().parent.parent / "examples" / "eobs"
SEV = {Severity.INFO: "[i]", Severity.WARNING: "[!]", Severity.ERROR: "[X]"}


def _print(result: DecodeResult) -> None:
    by_id = chunk_index(load_corpus())
    bar = "=" * 74
    print(bar)
    print(f"ClearAnswer — {result.eob_id}  |  arm: {result.arm}  |  model: {result.model}")
    print(f"mode: {result.mode}   (an EOB is not a bill)")
    print(bar)
    print(f"\nIn plain English: {result.summary}\n")

    if result.math_findings:
        print("MATH CHECK (computed in code, not by AI):")
        for f in result.math_findings:
            loc = f"line {f.line_id}" if f.line_id else "whole EOB"
            nums = (f"  expected {f.expected:,.2f} vs actual {f.actual:,.2f}"
                    if f.expected is not None else "")
            print(f"  {SEV[f.severity]} {loc} · {f.check}{nums}")
            print(f"      {f.detail}")
        print()

    for l in result.lines:
        owe = f"you owe ${l.you_owe:,.2f}" if l.you_owe is not None else "amount unclear"
        print(f"--- {l.line_id} · {l.category.value} · {owe}")
        print(f"    {l.explanation}")
        for c in l.citations:
            mark = "verified" if c.verified else "!! NOT VERIFIED — human review !!"
            title = by_id[c.chunk_id].title if c.chunk_id in by_id else "?"
            print(f"    source [{c.chunk_id}] {title} ({mark}): “{c.quote}”")
        if l.retrieval:
            terms = ", ".join(l.retrieval[0].matched_terms[:6])
            print(f"    retrieval: top match {l.retrieval[0].chunk_id} "
                  f"(BM25 {l.retrieval[0].score}; matched: {terms})")
        print()

    print("WHAT TO DO NEXT:")
    for i, a in enumerate(result.actions, 1):
        print(f"  {i}. {a}")

    if result.escalate:
        print(f"\n>> HUMAN HAND-OFF RECOMMENDED: {result.escalate_reason}")

    if result.groundedness:
        g = result.groundedness
        print(f"\nGroundedness guard: {g.verified_quotes}/{g.total_quotes} citations verified "
              f"against their cited source chunks.")
        for u in g.unverified:
            print(f"  ! {u}")
    print(bar)
    print("ClearAnswer explains documents; it does not give billing, legal, or medical")
    print("advice, and it never tells you to pay. All bundled data is synthetic.")


def cmd_decode(args: argparse.Namespace) -> int:
    eob = json.loads(Path(args.eob).read_text(encoding="utf-8"))
    offline = args.offline or not os.environ.get("ANTHROPIC_API_KEY")
    if offline and not args.offline:
        print("(no ANTHROPIC_API_KEY — replaying cached output from a real API run)\n")
    if offline:
        from .offline import run_offline
        result = run_offline(eob, args.arm)
    else:
        from .pipeline import run_decode
        result = run_decode(eob, args.arm)
    if args.json:
        print(result.to_json())
    else:
        _print(result)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from .report import write_report
    eob = json.loads(Path(args.eob).read_text(encoding="utf-8"))
    offline = args.offline or not os.environ.get("ANTHROPIC_API_KEY")
    if offline:
        from .offline import run_offline
        result = run_offline(eob, args.arm)
    else:
        from .pipeline import run_decode
        result = run_decode(eob, args.arm)
    path = write_report(result, eob, chunk_index(load_corpus()), Path(args.out))
    print(f"wrote {path}")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    for p in sorted(EOB_DIR.glob("*.json")):
        e = json.loads(p.read_text(encoding="utf-8"))
        print(f"{p.name}: {e.get('one_liner', '')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="clearanswer", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decode", help="Decode an EOB")
    d.add_argument("--eob", required=True)
    d.add_argument("--arm", default="worker+skill",
                   choices=["worker", "worker+skill", "teacher+skill"])
    d.add_argument("--offline", action="store_true")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=cmd_decode)
    r = sub.add_parser("report", help="Render the glass-box HTML report")
    r.add_argument("--eob", required=True)
    r.add_argument("--arm", default="worker+skill",
                   choices=["worker", "worker+skill", "teacher+skill"])
    r.add_argument("--offline", action="store_true")
    r.add_argument("--out", default="report")
    r.set_defaults(func=cmd_report)
    l = sub.add_parser("list-eobs", help="List bundled example EOBs")
    l.set_defaults(func=cmd_list)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
