"""Model calls for the three arms — pure standard library (urllib), no SDK needed.

  worker         — Haiku 4.5, no skill pack (baseline)
  worker+skill   — Haiku 4.5 + the Fable-5-authored skill pack (the product config)
  teacher+skill  — Fable 5 + skill pack (quality ceiling / eval reference)

The model NEVER does arithmetic (code does) and NEVER answers beyond the
retrieved chunks (guard verifies). Its job: plain language, correct category,
correct citations, correct next steps.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import MODEL_TEACHER, MODEL_WORKER

API_URL = "https://api.anthropic.com/v1/messages"
SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "eob-decoding.md"

ARMS = {
    "worker": (MODEL_WORKER, False),
    "worker+skill": (MODEL_WORKER, True),
    "teacher+skill": (MODEL_TEACHER, True),
}

SYSTEM = """You are ClearAnswer, an assistant that explains Explanation of Benefits (EOB) \
documents to health-plan members in plain language (8th-grade reading level).

Hard rules:
1. NEVER do arithmetic. Deterministic code has already verified all math; its findings are \
provided. Repeat its conclusions — do not compute your own.
2. Every statement about a code's meaning, a plan rule, or a member right MUST carry a \
citation: the chunk_id of a retrieved passage plus a short EXACT verbatim quote from it. \
Quotes are machine-verified; copy characters exactly.
3. Only use the retrieved chunks provided. If they don't cover something, say so and set \
"escalate": true with a reason — routing to a human is a feature, not a failure.
4. An EOB is not a bill. Never tell the member to pay anything; explain what the document \
says and what to verify before paying a provider bill.
5. Tone: calm, blame-free, action-first. No jargon without a one-phrase translation.

Respond with ONLY JSON:
{"summary": str, "total_you_owe": number|null,
 "lines": [{"line_id": str, "category": one of ["paid_in_full","preventive","deductible",
  "coinsurance","copay","denial_not_covered","bundled","timely_filing_writeoff",
  "nsa_protected","cob_other_payer","possible_error"],
  "explanation": str, "you_owe": number|null,
  "citations": [{"chunk_id": str, "quote": str}]}],
 "actions": [str], "escalate": bool, "escalate_reason": str|null}"""


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def load_skill() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def build_user_prompt(eob: dict, findings_json: str, retrieved: dict[str, list[dict]]) -> str:
    return (
        "EOB DOCUMENT (synthetic):\n" + json.dumps(eob, indent=2) +
        "\n\nDETERMINISTIC MATH FINDINGS (already verified in code — repeat, don't recompute):\n" +
        findings_json +
        "\n\nRETRIEVED PASSAGES per line (cite by chunk_id; quote verbatim):\n" +
        json.dumps(retrieved, indent=2)
    )


def _post(payload: dict, retries: int = 3) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set — use --offline for the demo mode.")
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:400]
            if e.code in (429, 500, 502, 503, 529) and attempt < retries - 1:
                time.sleep(4 * (attempt + 1))
                continue
            raise RuntimeError(f"API error {e.code}: {body}") from e
    raise RuntimeError("unreachable")


def call_model(arm: str, user_prompt: str) -> tuple[dict, dict, str]:
    """Returns (parsed_json, usage, model_id)."""
    model, use_skill = ARMS[arm]
    system = SYSTEM + ("\n\n=== SKILL PACK (authored by claude-fable-5) ===\n" + load_skill()
                       if use_skill else "")
    data = _post({
        "model": model,
        "max_tokens": 3500,
        "system": system,
        "messages": [{"role": "user", "content": user_prompt}],
    })
    usage = {"input_tokens": data["usage"]["input_tokens"],
             "output_tokens": data["usage"]["output_tokens"]}
    return _extract_json(data["content"][0]["text"]), usage, model
