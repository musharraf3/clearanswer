"""Deterministic math verification — the anti-black-box core.

Every dollar on the EOB is re-computed in plain Python BEFORE the model sees it.
The model explains; it never does arithmetic. Findings are injected into the
model's context and always shown to the user verbatim.

Checks:
  line_arithmetic   allowed - plan_paid == deductible + copay + coinsurance + not_covered
  coinsurance_rate  coinsurance ≈ plan rate × (allowed - deductible_applied), in-network
  duplicate_line    same CPT + same date of service appearing twice
  preventive_zero   ACA preventive services should cost the member $0 in-network
  co_group_billing  CO-group adjustments are provider write-offs — member never owes them
  oop_max           running out-of-pocket total vs the plan's OOP maximum
"""

from __future__ import annotations

from collections import Counter

from .models import MathFinding, Severity

TOL = 0.01


def _f(x) -> float:
    return round(float(x or 0.0), 2)


def check_eob(eob: dict, plan: dict) -> list[MathFinding]:
    findings: list[MathFinding] = []
    lines = eob["lines"]

    # duplicate detection
    key_counts = Counter((l["cpt"], l["date_of_service"]) for l in lines)
    for (cpt, dos), n in key_counts.items():
        if n > 1:
            ids = [l["line_id"] for l in lines if l["cpt"] == cpt and l["date_of_service"] == dos]
            findings.append(MathFinding(
                line_id=",".join(ids), check="duplicate_line", severity=Severity.ERROR,
                detail=f"CPT {cpt} on {dos} appears {n} times. Duplicate billing is one of the "
                       f"most common EOB errors — ask the provider for an itemized bill."))

    oop_before = _f(eob.get("oop_used_before", 0))
    oop_total = oop_before

    for l in lines:
        allowed, paid = _f(l["allowed"]), _f(l["plan_paid"])
        ded, copay, coins = _f(l.get("deductible", 0)), _f(l.get("copay", 0)), _f(l.get("coinsurance", 0))
        ncov, resp = _f(l.get("not_covered", 0)), _f(l["patient_resp"])
        lid = l["line_id"]

        expected_resp = round(ded + copay + coins + ncov, 2)
        if abs(resp - expected_resp) > TOL:
            findings.append(MathFinding(
                line_id=lid, check="line_arithmetic", severity=Severity.ERROR,
                detail="The 'you owe' amount does not equal deductible + copay + coinsurance + "
                       "not-covered for this line. Ask the plan to re-explain this amount.",
                expected=expected_resp, actual=resp))

        if abs((allowed - paid) - expected_resp) > TOL and abs(resp - expected_resp) <= TOL:
            findings.append(MathFinding(
                line_id=lid, check="line_arithmetic", severity=Severity.WARNING,
                detail="Allowed amount minus plan payment does not match the member portion; "
                       "part of the charge may have been adjusted without an explanation code.",
                expected=round(allowed - paid, 2), actual=expected_resp))

        if coins > 0 and l.get("network") == "in" and not l.get("deductible_phase"):
            rate = plan["coinsurance_rate_in_network"]
            exp_coins = round(rate * (allowed - ded), 2)
            if abs(coins - exp_coins) > 0.5:
                findings.append(MathFinding(
                    line_id=lid, check="coinsurance_rate", severity=Severity.WARNING,
                    detail=f"Coinsurance differs from the plan's in-network rate "
                           f"({int(rate*100)}% of allowed after deductible).",
                    expected=exp_coins, actual=coins))

        if l["cpt"] in set(plan["preventive_cpts"]) and l.get("network") == "in" and resp > 0:
            findings.append(MathFinding(
                line_id=lid, check="preventive_zero", severity=Severity.ERROR,
                detail="This is an ACA preventive service — in-network members should owe $0. "
                       "This charge is worth disputing.",
                expected=0.0, actual=resp))

        for code in l.get("codes", []):
            if code.startswith("CO-") and resp > 0 and _f(l.get("co_amount", 0)) > 0:
                if abs(resp - _f(l.get("co_amount", 0))) <= TOL:
                    findings.append(MathFinding(
                        line_id=lid, check="co_group_billing", severity=Severity.ERROR,
                        detail=f"Adjustment {code} is a CO (contractual obligation) group code — "
                               f"the provider writes this off. It should never appear as an "
                               f"amount you owe.", expected=0.0, actual=resp))

        oop_total = round(oop_total + ded + copay + coins, 2)

    oop_max = _f(plan["oop_max_individual"])
    if oop_total > oop_max + TOL:
        findings.append(MathFinding(
            line_id=None, check="oop_max", severity=Severity.ERROR,
            detail=f"Your running out-of-pocket total (${oop_total:,.2f}, including "
                   f"${oop_before:,.2f} already used this year) exceeds the plan's "
                   f"${oop_max:,.2f} out-of-pocket maximum. Amounts above the maximum "
                   f"are the plan's responsibility, not yours.",
            expected=oop_max, actual=oop_total))

    return findings
