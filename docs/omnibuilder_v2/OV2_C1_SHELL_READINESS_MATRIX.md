# OV2-C.1 — SHELL READINESS MATRIX

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Omniview V2 Product Shell
> **Status:** READINESS ASSESSMENT

---

## Section Readiness by Source

| # | Section | CT_TRIPS_2026 | YANGO_API_RAW | Overall | Blocker |
|---|---------|--------------|---------------|---------|---------|
| 1 | Executive State | OK | WARNING | WARNING | Yango: SHORT_SERIES (2d) |
| 2 | Source Health | OK | OK | OK | — |
| 3 | KPI Strip | OK | OK | OK | — |
| 4 | Plan vs Real | OK | BLOCKED | OK (CT) | Yango: no plan infrastructure |
| 5 | Growth Movement | OK | WARNING | WARNING | Yango: <7d data |
| 6 | Operational Coverage | OK | OK | OK | — |
| 7 | Revenue Integrity | WARNING | WARNING | WARNING | CT: delta=0% (self-ref), Yango: delta=-78% vs CT |
| 8 | Slice Readiness | OK | BLOCKED | OK (CT) | Yango: no slice data |
| 9 | Alerts / Warnings | OK | WARNING | WARNING | Yango: 3 active warnings |
| 10 | Lineage / Audit | OK | OK | OK | — |

---

## Status Counts

| Status | CT_TRIPS_2026 | YANGO_API_RAW | Combined |
|--------|--------------|---------------|----------|
| OK | 9 | 4 | — |
| WARNING | 1 | 4 | — |
| BLOCKED | 0 | 2 | — |
| NOT_READY | 0 | 0 | — |

---

## Blocker Details

### YANGO_API_RAW — Plan vs Real (BLOCKED)
- **Reason:** Yango API has no plan infrastructure. Plan tables (`ops.plan_*`) are CT-native.
- **Resolution:** When Yango becomes canonical, plan data must be projected from CT or ingested separately.
- **Impact:** Section hidden when source=YANGO_API_RAW.

### YANGO_API_RAW — Slice Readiness (BLOCKED)
- **Reason:** Yango API orders are not mapped to CT business slices. Slice dimension is CT-native.
- **Resolution:** Implement park→slice mapping in raw_yango MVs or staging.
- **Impact:** Section hidden when source=YANGO_API_RAW.

---

## Warnings Detail

| Section | Source | Warning | Severity |
|---------|--------|---------|----------|
| Executive State | YANGO | Only 2 days of data (SHORT_SERIES) | warning |
| Revenue Integrity | CT | CT self-referencing (revenue vs itself) | info |
| Revenue Integrity | YANGO | Revenue delta -78.46% vs CT | warning |
| Growth Movement | YANGO | Short series — cannot compute WoW/MoM | warning |
| Alerts | YANGO | PARTIAL_PARK_COVERAGE, API_COVERAGE_WARNING, CANONICAL_NOT_READY | warning/critical |

---

## Governance

| Rule | Status |
|------|--------|
| No UI touched | PASS |
| No Omniview V1 touched | PASS |
| No serving productivo replaced | PASS |
| canonical_ready explicit | PASS |
| Future sources accommodated | PASS |
