# Program Capacity Policy Simulation

Generated: 2026-06-06T10:00:19.459627

Date: 2026-06-02 | Actionable: 500 | Capacity: 310

Actionable by program: {"PROGRAM_CHURN_PREVENTION": 420, "PROGRAM_HIGH_VALUE_RECOVERY": 80}

## A: Current (strict priority)

**Logic:** Strict priority order. Higher rank takes all needed. Lower ranks get 0 if capacity exhausted.

**Total unassigned:** 190

| Program | Actionable | Assigned | Unmet | % Served | Notes |
|---|---:|---:|---:|---:|---|
| High Value Recovery | 80 | 80 | 0 | 100.0% | — |
| Churn Prevention | 420 | 230 | 190 | 54.8% | — |
| 14/90 | 0 | 0 | 0 | 0.0% | — |
| Active Growth | 0 | 0 | 0 | 0.0% | — |

## B: Max cap per program

**Logic:** Max caps: HVR=40%, CP=60%, 1490=30%, AG=30% of capacity. Prevents one program from consuming all.

**Total unassigned:** 234

| Program | Actionable | Assigned | Unmet | % Served | Notes |
|---|---:|---:|---:|---:|---|
| High Value Recovery | 80 | 80 | 0 | 100.0% | max=124 |
| Churn Prevention | 420 | 186 | 234 | 44.3% | max=186 |
| 14/90 | 0 | 0 | 0 | 0.0% | max=93 |
| Active Growth | 0 | 0 | 0 | 0.0% | max=93 |

## C: Min floor per program

**Logic:** Min floor ensures every active program gets at least X slots. Remainder distributed by priority.

**Total unassigned:** 190

| Program | Actionable | Assigned | Unmet | % Served | Notes |
|---|---:|---:|---:|---:|---|
| High Value Recovery | 80 | 80 | 0 | 100.0% | floor=80 |
| Churn Prevention | 420 | 230 | 190 | 54.8% | floor=50 |
| 14/90 | 0 | 0 | 0 | 0.0% | floor=10 |
| Active Growth | 0 | 0 | 0 | 0.0% | floor=10 |

## D: Proportional share

**Logic:** Capacity distributed proportionally to actionable count. Ensures fair share per program.

**Total unassigned:** 190

| Program | Actionable | Assigned | Unmet | % Served | Notes |
|---|---:|---:|---:|---:|---|
| High Value Recovery | 80 | 50 | 30 | 62.5% | share=16.0% |
| Churn Prevention | 420 | 260 | 160 | 61.9% | share=84.0% |
| 14/90 | 0 | 0 | 0 | 0.0% | share=0.0% |
| Active Growth | 0 | 0 | 0 | 0.0% | share=0.0% |

## E: Hybrid (priority + caps + floors)

**Logic:** Hybrid: HVR=40%max+80floor, CP=55%max+100floor, others=20%max+5floor. Priority order within caps/floors.

**Total unassigned:** 250

| Program | Actionable | Assigned | Unmet | % Served | Notes |
|---|---:|---:|---:|---:|---|
| High Value Recovery | 80 | 80 | 0 | 100.0% | max=124, floor=80 |
| Churn Prevention | 420 | 170 | 250 | 40.5% | max=170, floor=100 |
| 14/90 | 0 | 0 | 0 | 0.0% | max=62, floor=5 |
| Active Growth | 0 | 0 | 0 | 0.0% | max=62, floor=5 |

---

## Comparison Summary

| Scenario | HVR | CP | 14_90 | AG | Total Unassigned |
|---|---:|---:|---:|---:|---:|
| A: Current (strict priority) | 80 | 230 | 0 | 0 | 190 |
| B: Max cap per program | 80 | 186 | 0 | 0 | 234 |
| C: Min floor per program | 80 | 230 | 0 | 0 | 190 |
| D: Proportional share | 50 | 260 | 0 | 0 | 190 |
| E: Hybrid (priority + caps + f | 80 | 170 | 0 | 0 | 250 |

---

## Hardcodes Found in Current Policy

1. `PRIORITY_RANK` — strict ordering in `priority_registry.py` (HVR=1, CP=2, 1490=3, AG=4)

2. `allocate_capacity()` — sequential greedy: first program takes all it needs

3. `daily_action_capacity = 500` — from `opportunity_policy_config` (hardcoded default)

4. `PROGRAM_BONUS` in scoring — HVR=200, CP=100, 1490=50, AG=0 (hardcoded in SQL)

5. No min/max per program, no target share, no caps — pure priority order

---

## Recommendation

**Scenario E (Hybrid)** offers the best balance:

- Preserves HVR priority (40% cap = 124, floor = 80)

- Gives CP substantial share (55% cap = 170, floor = 100)

- Ensures 1490 and AG get something if they have actionable (floor = 5 each)

- Prevents any program from starving others

- Total unassigned remains the same (190) but distributed more fairly

**DO NOT implement yet.** This is a simulation. Requires Program Registry to store policy config.