# EOB Decoding Skill

**Authored by:** `claude-fable-5` (teacher model) · **Consumed by:** any worker model
**Purpose:** distilled domain expertise for decoding Explanation of Benefits documents.
This file is the "expensive model's knowledge, packaged for the cheap model."

---

## 1. Decision tree for line categories

Work through these questions IN ORDER for each line; stop at the first match:

1. Code-verified math finding of severity ERROR touches this line → `possible_error`
   (still explain the underlying service, but the category must surface the problem).
2. CPT is in the plan's preventive list, network is "in" → `preventive`
   (if patient_resp > 0, the math checker will have flagged it — see rule 1).
3. Codes include CO-29 → `timely_filing_writeoff`. Member owes nothing; say so plainly.
4. Codes include CO-97 → `bundled`. Provider cannot bill the member for this line.
5. Emergency place of service + out-of-network → `nsa_protected` (cite RIGHT-NSA-ER).
   Non-chosen specialist (anesthesia/radiology/pathology) at in-network facility →
   `nsa_protected` (cite RIGHT-NSA-FACILITY).
6. Codes include OA-23 → `cob_other_payer`.
7. Codes include PR-204 or a denial reason with member liability → `denial_not_covered`.
   ALWAYS pair with appeal citations (RIGHT-APPEAL-INT, and RIGHT-APPEAL-EXT for
   medical-necessity denials).
8. patient_resp == 0 and plan paid → `paid_in_full`.
9. Deductible dollars dominate the member share → `deductible`; copay only → `copay`;
   otherwise coinsurance present → `coinsurance`. Mixed lines: pick the largest component
   and mention the others in the explanation.

## 2. Non-negotiable domain rules

- **CO vs PR is the liability question.** CO = provider's write-off, member NEVER owes it.
  PR = legitimate member cost under the plan design. Any CO amount appearing in the
  member's "you owe" column is a red flag worth a dispute.
- **Coinsurance is always a % of the ALLOWED amount**, never of billed charges. If a
  member's share looks like a % of billed, something is wrong.
- **An EOB is not a bill.** Never instruct payment. The correct verb is "verify":
  compare the provider's bill to this EOB before paying anything.
- **Denials are the start of a process, not the end.** Every denial explanation must
  state the appeal right and the 180-day window, and medical-necessity denials must
  mention external review (they are commonly overturned there).
- **Emergency = in-network cost sharing, always.** Network status of an ER is irrelevant
  to what the member owes, per the No Surprises Act.
- **$0 preventive is federal law in-network.** Any member charge on a listed preventive
  service is presumptively an error, not a benefit design choice.

## 3. Explanation style (member-facing)

- 8th-grade reading level. Short sentences. One idea per sentence.
- Translate every code inline: "CO-45 (the discount your provider agreed to)".
- Lead with what it means for their wallet, then why: "You owe $24 for this lab. That is
  your 20% share of the plan's approved price."
- Never blame the member. Never speculate about provider intent — describe the pattern
  ("this looks like a duplicate") and the remedy (itemized bill).
- Dollar amounts: always name the source column ("the plan's allowed amount of $120").

## 4. Actions section — always concrete

Good: "Call Lakeside Imaging's billing office (number on their bill) and ask why CPT
80053 appears twice for March 12." Bad: "Contact your provider with questions."
Cap at 4 actions, ordered by urgency. If any ERROR-severity finding exists, action #1
is always: do not pay the provider's bill until this is resolved.

## 5. Escalation triggers (set "escalate": true)

- Any ERROR-severity math finding (code sets this automatically; agree with it).
- The retrieved chunks do not actually answer what the line needs (do not improvise).
- Amounts you cannot tie to a plan rule or a code definition.
- The member would owe more than $1,000 on a single denied line (high stakes → human).

## 6. Worked exemplars

**Deductible line (PR-1, $850 MRI):**
"You owe $850 for this MRI. You had not yet met your $1,500 yearly deductible, so this
approved amount goes to your deductible first [CODE-PR-1]. The good news: the $950
difference between the $1,800 charge and the plan's $850 approved price is written off
by your provider [CODE-CO-45] — you never owe that part."

**Timely-filing line wrongly billed to member (CO-29 with patient_resp > 0):**
"The plan rejected this claim because your provider submitted it after the filing
deadline. That is the provider's error, not yours — CO-29 write-offs are the provider's
responsibility [CODE-CO-29], and the code checker confirms this amount should not be in
your column [GRP-CO]. If a bill arrives for it, dispute it in writing."

**NSA emergency line (out-of-network ER):**
"Even though this hospital was outside your network, this was emergency care, so federal
law caps your share at normal in-network amounts [RIGHT-NSA-ER]. The hospital is not
allowed to bill you for the difference."
