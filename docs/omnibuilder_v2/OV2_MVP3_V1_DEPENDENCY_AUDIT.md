# OV2-MVP.3 — V1 DEPENDENCY AUDIT

> **Fase:** OV2-MVP.3 — Operational Acceptance Trial
> **Sub-document:** V1 Dependency Audit
> **Fecha:** 2026-06-12

---

## WHAT FORCES A RETURN TO V1?

| # | Task | V1 Screen | Severity | Reason | Gap |
|---|------|-----------|----------|--------|-----|
| 1 | Ver commission % con datos reales | OmniMatrix | **MEDIUM** | commission_pct pipeline no poblado. V2 muestra N/A. | Data pipeline |
| 2 | Ver reportes ECharts (barras/líneas) | Reportes | **LOW** | V2 no tiene ECharts reports. Operador puede usar matrix + filtros en su lugar. | ECharts not ported |
| 3 | Ver Momentum drill (tendencia WoW chart) | Inspect → Momentum | **LOW** | V2 cell inspector tiene drill pero no chart ECharts. Delta arrows son alternativa. | ECharts not ported |
| 4 | Ver Plan vs Real daily/weekly | PvR view | **LOW** | V2 PvR es solo monthly. Day/week requiere data pipeline adicional. | Day/week PvR |
| 5 | Ver Operational Status Bar detallada | StatusBar | **LOW** | V1 status bar es mas detallada (RAW→day→week→month chain). V2 status bar es mas simple. | Governance chain |
| 6 | Exportar datos a CSV/PDF | — | **LOW** | V1 no tiene export tampoco. Ambos carecen de esta capacidad. | Export (P3) |
| 7 | Backfill / refresh control | FactStatusPanel | **LOW** | Dev-ops concern. Operadores no deberian usar backfill. | Backfill controls |
| 8 | Ver Control Loop PvR | CL PvR view | **LOW** | Vista standalone de control loop. No es tarea operacional diaria. | CL PvR |
| 9 | Ver Real Operational snapshot | Real Ops view | **LOW** | Today/yesterday snapshot. Sustituible por V2 matrix day. | Real Ops |

---

## SEVERITY CLASSIFICATION

| Severity | Count | Tasks |
|----------|-------|-------|
| NONE | 0 | — |
| LOW | 8 | Tasks 2-9 |
| MEDIUM | 1 | Task 1 (commission) |
| HIGH | 0 | — |
| CRITICAL | 0 | — |

---

## VERDICT

**No critical V1 dependencies.** The only medium-severity dependency is commission_pct (data pipeline gap, not V2 code issue). All other dependencies are LOW: ECharts views, Momentum charts, day/week PvR — none are daily operational blockers.

**An operator CAN work a full day without V1.** The operator would miss: commission % (N/A), ECharts charts (matrix is sufficient), Momentum trends (delta arrows are sufficient).
