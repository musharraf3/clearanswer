# ClearAnswer eval results

Generated 2026-07-11 · 10 synthetic EOB cases · all numbers from REAL API runs
(cached in `examples/outputs/`; math-flag detection is deterministic code and identical across arms).

| Arm | Model | Line category acc. | Must-mention coverage | Citation groundedness | Escalation acc. | FK grade | Total cost |
|---|---|---|---|---|---|---|---|
| worker | claude-haiku-4-5-20251001 | 13/16 (81%) | 21/26 (81%) | 29/29 (100%) | 10/10 | 8.0 | $0.0527 |
| worker+skill | claude-haiku-4-5-20251001 | 14/14 (100%) | 22/26 (85%) | 32/32 (100%) | 10/10 | 7.8 | $0.0704 |
| teacher+skill | claude-fable-5 | 14/14 (100%) | 20/26 (77%) | 37/37 (100%) | 9/10 | 8.0 | $1.0823 |

**Reading the table:** "worker" is Haiku 4.5 alone; "worker+skill" adds the skill pack
authored by Claude Fable 5 (`skills/eob-decoding.md`); "teacher+skill" is Fable 5 itself,
as the quality ceiling. The product bet: worker+skill ≈ teacher quality at ~10x lower cost.
Prices: Haiku 4.5 $1/$5 per 1M tokens; Fable 5 $10/$50 per 1M tokens (list, July 2026).
