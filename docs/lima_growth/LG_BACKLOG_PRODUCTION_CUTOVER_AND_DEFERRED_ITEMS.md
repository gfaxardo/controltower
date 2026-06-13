# LG-BACKLOG — Production Cutover Active & Deferred Items

**Date:** 2026-06-13
**Reference:** `LG_PROD_SCOPE_1A_PRODUCTION_CUTOVER_SCOPE_OVERRIDE.md`
**Purpose:** Formal separation of production cutover items from deferred backlog.

---

## Production Cutover Active

These items are **authorized for implementation** under the Production Cutover Exception. They must be complete before Monday production GO/NO-GO.

| # | Item | Gate | Owner | Status |
|---|------|------|-------|--------|
| 1 | Exclusive Program Assignment Contract | Gate 1 | Growth Machine | PENDING |
| 2 | Program criteria freeze | Gate 1 | Growth Machine | PENDING |
| 3 | Dry-run exclusive assignment counts | Gate 2 | Growth Machine | PENDING |
| 4 | Deterministic assignment resolution (1 driver = 1 program) | Gate 3 | Growth Machine | PENDING |
| 5 | Explorer synchronization with new assignment | Gate 3 | Growth Machine | PENDING |
| 6 | Programs/Explorer reconciliation | Gate 3 | Growth Machine | PENDING |
| 7 | Opportunity list regeneration (exclusive assignment) | Gate 3 | Growth Machine | PENDING |
| 8 | Backend/API smoke tests | Gate 4 | Growth Machine | PENDING |
| 9 | UI validation (Explorer, Programs, Opportunity) | Gate 5 | Growth Machine | PENDING |
| 10 | Production GO/NO-GO decision | Gate 6 | Operator | PENDING |

---

## Deferred — Not Blocking Monday

These items are **explicitly deferred** and NOT authorized by the Production Cutover Exception. They remain in backlog.

| # | Item | Reason | Blocks Monday? | Future Phase |
|---|------|--------|---------------|-------------|
| 1 | `driver_history_weekly` week 06-08 observation | Weekly cycle evidence for CLOSED declaration | NO | Post-Monday FH-1C check |
| 2 | Program Registry V3 | Complete program registry redesign | NO | Post-closure Growth |
| 3 | Lifecycle State Machine | Complete state machine implementation | NO | Post-closure Growth |
| 4 | Temporal Program Assignment Engine | Time-based assignment rules | NO | Post-closure Growth |
| 5 | Program label/copy layer (tooltips) | "Why this program?" operator context | NO | Program Registry V3 |
| 6 | Eligibility column in Explorer | Show eligible programs alongside assigned | NO | Program Registry V3 |
| 7 | Stale assignment badge | Visual indicator for outdated program labels | NO | Program Registry V3 |
| 8 | Program transition explainability | Why driver moved programs | NO | State Machine |
| 9 | Priority comparison in Explorer | Multi-eligible priority ranking | NO | Program Registry V3 |
| 10 | High-perf CHURN explanation context | Context for high-performance churn cases | NO | Health Contract V2 |
| 11 | Age-out indicator for 14_90 | Alert when driver outgrows 14_90 | NO | Program Migration Rules |
| 12 | NONE-assigned driver investigation | Drivers with no program assignment | NO | Program Registry V3 |
| 13 | Top Performer Program | Reward/highlight top performers | NO | Post-closure Growth |
| 14 | Health Contract V2 | Enhanced health monitoring | NO | Post-closure Growth |
| 15 | Control Loop V2 | Enhanced control loop | NO | Post-closure Growth |
| 16 | Queue V2 | Enhanced queue management | NO | Post-closure Growth |
| 17 | Execution Layer | Action execution framework | NO | Post-closure Growth |
| 18 | Diagnostic Engine 2A.3 | Behavioral pattern diagnosis | NO | Post-OMNI-P0 Closure |
| 19 | Commission Measurement Layer | Commission tracking and measurement | NO | Post-closure Growth |
| 20 | Movement Scoring | Segment movement scoring | NO | Post-closure Growth |
| 21 | RNA Scoring Hardening | RNA priority scoring improvements | NO | Post-closure Growth |

---

## Gate Summary

| Gate | Name | Status | Blocked by Backlog? |
|------|------|--------|---------------------|
| Gate 1 | Contract Freeze | PENDING | NO |
| Gate 2 | Dry-Run Counts | PENDING | NO |
| Gate 3 | Implementation | PENDING | NO |
| Gate 4 | Backend/API Smoke | PENDING | NO |
| Gate 5 | UI Validation | PENDING | NO |
| Gate 6 | Production GO/NO-GO | PENDING | NO |

---

*Backlog preserved. Production cutover scope is isolated from deferred items. No deferred item blocks Monday readiness.*
