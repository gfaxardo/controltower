# CF-H1 Precheck — Control Foundation Metric Hardening

## Fecha: 2026-05-29
## Motor: Control Foundation
## Fase: H1 — Metric Definition & Weekly Distinct Hardening

---

## ACTIVE PHASE

- **Motor**: Control Foundation
- **Phase**: 1H.4 — Operational Maturity Governance Layer
- **Status**: ACTIVE (per `ai_current_phase.md`)

## READY NEXT

- **Motor**: Diagnostic Engine
- **Phase**: 2A.3 — Behavioral Pattern Diagnosis
- **Status**: READY NEXT (blocked until Serving Governance Foundation is stabilized)

---

## GO / NO-GO FOR CF-H1: **GO**

Control Foundation is the only active motor. Metric hardening is a prerequisite for ALL downstream engines (Diagnostic → Forecast → Priority → Decision).

This work is:
- In-scope for Control Foundation closure rules
- Required before any Priority Layer work
- Required before any cross-grain decisions

---

## RELATIONSHIP WITH CONTROL FOUNDATION

Control Foundation closure rules (from `ai_operating_system.md`):

| Rule | Status | CF-H1 Impact |
|------|--------|-------------|
| KPIs reconcile | **PARTIAL** — active_drivers weekly has SUM proxy vs true distinct | **DIRECTLY ADDRESSED** |
| Grains are consistent | **PARTIAL** — daily is correct, monthly is correct, weekly is a rollup with known bug | **DIRECTLY ADDRESSED** |
| Serving facts are governed | OK | Not impacted |
| Freshness works | OK (per-KPI freshness applied) | Verified |
| Runtime fallback is protected | OK | Not impacted |
| Performance is stable | OK | Not impacted |
| UI does not freeze | OK | Not impacted |
| Plan vs Real is trustworthy | **PARTIAL** — weekly plan vs real for active_drivers uses inflated real values | **DIRECTLY ADDRESSED** |

---

## RISKS IF IGNORED

| Risk | Probability | Impact | Engine Affected |
|------|------------|--------|-----------------|
| Priority Layer scores weekly active_drivers attainment incorrectly | HIGH | HIGH | Priority, Decision |
| Gap alerts for active_drivers in weekly grain are misleading | HIGH | HIGH | Alerting, Operational |
| Loyalty programs based on weekly driver counts get wrong data | MEDIUM | HIGH | Loyalty |
| Cross-grain reconciliation reports show phantom discrepancies | LOW | MEDIUM | Diagnostic |
| Operators make decisions on inflated driver numbers | HIGH | HIGH | Operational, Decision |
| Benchmarking across weeks is inconsistent (some weeks 7 days, some 7 days but partial) | MEDIUM | MEDIUM | Diagnostic, Benchmarking |

---

## DOCUMENTS REVIEWED

- `ai_operating_system.md` — Engine order, closure rules, serving-first architecture
- `ai_current_phase.md` — Active phase = Control Foundation 1H.4
- `docs/omniview/OMNIVIEW_REAL_USER_NAVIGATION_REPORT.md` — CONDITIONAL GO, H-2 = weekly distinct bug
- `docs/omniview/ACTIVE_DRIVERS_FRESHNESS_MISMATCH_REPORT.md` — Freshness per KPI implemented
- `docs/omniview/OMNIVIEW_REAL_NAVIGATION_BUGLIST.md` — H-2: weekly SUM proxy
