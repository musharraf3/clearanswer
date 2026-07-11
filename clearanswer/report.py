"""HTML report renderer — the ClearAnswer 'glass box' UI.

One self-contained HTML file per decode: no JavaScript frameworks, no build
step, no external assets. Every panel exposes the machinery: code-computed
math findings, BM25 retrieval scores with matched terms, and per-citation
verification status. Transparency is the interface.
"""

from __future__ import annotations

import html
from pathlib import Path

from .corpus import Chunk
from .models import DecodeResult, Severity

CSS = """
:root{--ink:#1a202c;--sub:#5a6472;--line:#e2e8f0;--brand:#0e6e6b;--brand-lt:#e6f4f3;
--ok:#1a7f37;--ok-bg:#e8f5ec;--warn:#9a6700;--warn-bg:#fff8e5;--err:#b42318;--err-bg:#fdecea;
--chip:#eef2f7}
*{box-sizing:border-box;margin:0}
body{font-family:'Segoe UI',system-ui,-apple-system,Arial,sans-serif;color:var(--ink);
background:#f5f7fa;padding:28px;line-height:1.55}
.wrap{max-width:880px;margin:0 auto}
header{display:flex;align-items:baseline;gap:14px;margin-bottom:6px}
header h1{font-size:26px;color:var(--brand)}
header .tag{color:var(--sub);font-size:13px}
.banner{background:var(--brand-lt);border:1px solid var(--brand);color:var(--brand);
border-radius:10px;padding:10px 16px;font-weight:600;margin:14px 0}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px 20px;
margin:14px 0;box-shadow:0 1px 2px rgba(16,24,40,.04)}
.card h2{font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:var(--sub);
margin-bottom:10px}
.summary{font-size:17px}
.finding{border-left:4px solid;border-radius:6px;padding:10px 14px;margin:8px 0;font-size:14px}
.finding.error{border-color:var(--err);background:var(--err-bg)}
.finding.warning{border-color:var(--warn);background:var(--warn-bg)}
.finding.info{border-color:var(--sub);background:var(--chip)}
.finding .nums{font-family:Consolas,monospace;font-size:13px;color:var(--sub)}
.badge{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;
padding:2px 9px;border-radius:999px;text-transform:uppercase}
.badge.code{background:#102a43;color:#fff}
.badge.cat{background:var(--chip);color:var(--ink)}
.badge.err{background:var(--err-bg);color:var(--err)}
.badge.ok{background:var(--ok-bg);color:var(--ok)}
.line-head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.owe{font-size:20px;font-weight:700}
.cite{background:#fafbfc;border:1px solid var(--line);border-radius:8px;padding:8px 12px;
margin:8px 0 0;font-size:13.5px}
.cite .src{color:var(--brand);font-weight:600}
.cite .q{font-style:italic;color:var(--sub)}
.retr{font-size:12.5px;color:var(--sub);margin-top:8px;font-family:Consolas,monospace}
.retr .bar{display:inline-block;height:8px;background:var(--brand);border-radius:4px;
vertical-align:middle;margin-right:6px}
.actions li{margin:6px 0 6px 4px}
.escalate{background:var(--warn-bg);border:1.5px solid var(--warn);color:var(--warn);
border-radius:10px;padding:12px 16px;font-weight:600;margin:14px 0}
footer{color:var(--sub);font-size:12.5px;margin-top:18px;border-top:1px solid var(--line);
padding-top:12px}
.gg{font-weight:600}
"""


def _e(t) -> str:
    return html.escape(str(t))


def render(result: DecodeResult, eob: dict, by_id: dict[str, Chunk]) -> str:
    max_score = max((r.score for l in result.lines for r in l.retrieval), default=1.0) or 1.0
    parts = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>ClearAnswer — {_e(result.eob_id)}</title><style>{CSS}</style></head><body><div class="wrap">
<header><h1>ClearAnswer</h1><span class="tag">glass-box EOB decoder ·
claim {_e(eob.get("claim_id","?"))} · {_e(result.model)} · arm: {_e(result.arm)}</span></header>
<div class="banner">This is an explanation of your EOB. An EOB is <u>not a bill</u> —
compare it with your provider's bill before paying anything.</div>
<div class="card"><h2>In plain English</h2><p class="summary">{_e(result.summary)}</p></div>"""]

    if result.math_findings:
        rows = []
        for f in result.math_findings:
            nums = (f'<div class="nums">expected ${f.expected:,.2f} · shown ${f.actual:,.2f}</div>'
                    if f.expected is not None else "")
            loc = f"line {f.line_id}" if f.line_id else "whole EOB"
            rows.append(f'<div class="finding {f.severity.value}"><b>{_e(f.check)}</b> · {_e(loc)}'
                        f'<div>{_e(f.detail)}</div>{nums}</div>')
        parts.append(f'<div class="card"><h2>Math check <span class="badge code">computed in '
                     f'code — not by AI</span></h2>{"".join(rows)}</div>')
    else:
        parts.append('<div class="card"><h2>Math check <span class="badge code">computed in '
                     'code — not by AI</span></h2><div class="finding info">Every line adds up. '
                     'No duplicates, no out-of-pocket overcharges detected.</div></div>')

    for l in result.lines:
        owe = f"${l.you_owe:,.2f}" if l.you_owe is not None else "—"
        cites = []
        for c in l.citations:
            mark = ('<span class="badge ok">verified</span>' if c.verified
                    else '<span class="badge err">not verified — human review</span>')
            title = by_id[c.chunk_id].title if c.chunk_id in by_id else "unknown source"
            cites.append(f'<div class="cite"><span class="src">[{_e(c.chunk_id)}] {_e(title)}'
                         f'</span> {mark}<div class="q">“{_e(c.quote)}”</div></div>')
        retr = ""
        if l.retrieval:
            spans = []
            for r in l.retrieval[:3]:
                w = max(6, int(70 * r.score / max_score))
                spans.append(f'<div><span class="bar" style="width:{w}px"></span>'
                             f'{_e(r.chunk_id)} · BM25 {r.score:g} · matched: '
                             f'{_e(", ".join(r.matched_terms[:6]))}</div>')
            retr = f'<div class="retr"><b>why these sources (retrieval scores):</b>{"".join(spans)}</div>'
        parts.append(f"""<div class="card"><div class="line-head">
<div><span class="badge cat">{_e(l.category.value.replace("_"," "))}</span>
<b> {_e(l.line_id)}</b></div><div class="owe">you owe {owe}</div></div>
<p style="margin-top:8px">{_e(l.explanation)}</p>{"".join(cites)}{retr}</div>""")

    acts = "".join(f"<li>{_e(a)}</li>" for a in result.actions)
    parts.append(f'<div class="card"><h2>What to do next</h2><ol class="actions">{acts}</ol></div>')

    if result.escalate:
        parts.append(f'<div class="escalate">⚠ Human hand-off recommended: '
                     f'{_e(result.escalate_reason)}</div>')

    g = result.groundedness
    gg = (f'{g.verified_quotes}/{g.total_quotes} citations verified verbatim against their '
          f'cited sources' if g else "n/a")
    parts.append(f"""<footer><span class="gg">Groundedness guard: {gg}.</span>
Retrieval, math, and citation checks are deterministic code — inspect them in the repo.
ClearAnswer explains documents; it does not give billing, legal, or medical advice.
All data on this page is synthetic.</footer></div></body></html>""")
    return "".join(parts)


def write_report(result: DecodeResult, eob: dict, by_id: dict[str, Chunk], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result.eob_id}__{result.arm.replace('+', '_')}.html"
    path.write_text(render(result, eob, by_id), encoding="utf-8")
    return path
