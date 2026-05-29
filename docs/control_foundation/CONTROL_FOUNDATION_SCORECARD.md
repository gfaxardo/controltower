# Control Foundation Scorecard — Omniview Matrix

## Fecha: 2026-05-29

---

| Área | Estado | Evidencia |
|------|--------|-----------|
| **Freshness** | GO | Per-KPI freshness engine. `compute_kpi_freshness()` en backend. Badge amber/red en UI cuando KPI difiere del global. |
| **Projection** | GO | Plan vs Real funcional. `buildProjectionMatrix()`. Attainment, gap, signal. Serving fact pre-materializado. |
| **Runtime** | GO | Race protection (`requestIdRef`). Debounce 600ms. AbortController. Guardrails: requiere country para W/D. Sin recursion. |
| **Active Drivers** | GO | Daily/monthly: `COUNT(DISTINCT)` canónico. Weekly: corregido (CF-H1). Per-KPI freshness. Badge "≠Σ" para semi-additive. |
| **Revenue** | GO | `comision_empresa_asociada` certificado. Proxy documentado. GMV separado. Sin cambios de fórmula por fecha. |
| **KPI Registry** | GO | 5 KPIs auditados. Definiciones documentadas. Fuentes, fórmulas, grains, freshness por KPI. |
| **Scroll** | GO | Anchor scroll funcional. `scrollToCurrentPeriod()`. `userHasScrolledRef`. Smooth scroll. |
| **Scanability** | GO | Weekly focus filter. Weekday focus filter. Period states (closed/partial/future). Badge "ÚLTIMO CIERRE". |
| **Closed Period** | GO | `resolveClosedPeriodAnchor()`. Per-KPI anchor. "Ir al cierre" button. Calendar vs operational distinction. |
| **Delta** | GO | `computeProjectionDeltas()`. `buildComparableDelta()`. DoD/WoW/MoM via `periodPop`. L1/L2/L3 display model. |
| **Alerting** | CONDITIONAL | Engine exists but not activated for Priority Layer. `computeAlertsForMatrix()` listo para RC-1. |
| **Build** | GO | Frontend: 11.52s, 0 errors. Backend: 5/5 files PASS. |

---

## Resumen

| Clasificación | Count |
|---------------|-------|
| GO | 11 |
| CONDITIONAL GO | 1 (alerting — requiere RC-1 para activarse) |
| NO-GO | 0 |

---

## Control Foundation Status: **CLOSED**

Todas las áreas críticas para Control Foundation están certificadas. Los KPIs son consistentes cross-grain. La frescura funciona per-KPI. El revenue está definido y auditado. El runtime es estable.

El único ítem condicional (Alerting) no es parte de Control Foundation — es el primer componente de RC-1 Priority Layer.
