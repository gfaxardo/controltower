# OV2-MVP.3 — CRITICAL TASK INVENTORY

> **Fase:** OV2-MVP.3 — Operational Acceptance Trial
> **Sub-document:** Critical Task Inventory
> **Fecha:** 2026-06-12
> **Source:** V1 operational flows + V2 capabilities

---

## TASK CATALOG (Real Operational Tasks, Not Speculative)

### DAILY FLEET MONITORING (Operator)

| # | Task | V1 Path | V2 Path | Priority |
|---|------|---------|---------|----------|
| 1 | Ver trips del dia anterior | `/operacion/omniview-matrix` → day | `/operacion/omniview-v2-shadow` → day | P0 |
| 2 | Ver drivers activos | Matrix → active_drivers | Matrix → Drivers KPI | P0 |
| 3 | Ver revenue total | Matrix → revenue | Matrix → Revenue KPI | P0 |
| 4 | Ver freshness | OperationalStatusBar | Status bar | P0 |
| 5 | Ver por ciudad | City filter | City filter | P1 |
| 6 | Ver por business slice | Matrix rows | Matrix rows | P0 |
| 7 | Cambiar fecha | Date picker | Date inputs | P0 |

### WEEKLY PERFORMANCE REVIEW (Manager)

| # | Task | V1 Path | V2 Path | Priority |
|---|------|---------|---------|----------|
| 8 | Ver WoW trips | `/operacion/omniview-matrix` → week | grain: week | P0 |
| 9 | Comparar 2 semanas | Matrix current/previous | Delta arrows + delta % | P0 |
| 10 | Ver por parque | City + subfleet | Park dropdown | P1 |
| 11 | Ver commission | Matrix → commission_pct | KPI selector → Comm% | P1 |

### MONTHLY CLOSURE (Analyst)

| # | Task | V1 Path | V2 Path | Priority |
|---|------|---------|---------|----------|
| 12 | Ver MoM trips | `/operacion/omniview-matrix` → month | grain: month | P0 |
| 13 | Ver Plan vs Real | Plan vs Real view | Plan vs Real (Monthly) button | P0 |
| 14 | Ver revenue mensual | Matrix → revenue | Matrix → Revenue KPI | P0 |

### DEEP DIVE (Analyst)

| # | Task | V1 Path | V2 Path | Priority |
|---|------|---------|---------|----------|
| 15 | Inspeccionar celda | Click cell → inspector | Click cell → drawer | P1 |
| 16 | Ver top drivers | Inspector → momentum | Cell drill → top drivers | P1 |
| 17 | Ver distribución por park | Inspector → drill | Cell drill → parks | P1 |
| 18 | Ver source de datos | No explícito (implícito CT) | Source badge CT/YANGO | P1 |
| 19 | Ver estado de trust | Trust badge (V1) | Cell status + canonical badge | P1 |

### REPORTING (Revenue)

| # | Task | V1 Path | V2 Path | Priority |
|---|------|---------|---------|----------|
| 20 | Ver GMV | No disponible en V1 | Yango source → gmv | P1 |
| 21 | Exportar a reporte | V1 Reports view (ECharts) | Not available in V2 | P2 |

---

## TASK COUNT

| Category | Count |
|----------|-------|
| Daily Fleet Monitoring | 7 |
| Weekly Performance Review | 4 |
| Monthly Closure | 3 |
| Deep Dive | 5 |
| Reporting | 2 |
| **TOTAL** | **21 tasks** |

---

## PRIORITY DISTRIBUTION

| Priority | Count | V2 Ready |
|----------|-------|----------|
| P0 | 9 | 9/9 |
| P1 | 10 | 10/10 |
| P2 | 2 | 0/2 (ECharts reports not yet ported) |

**V2 readiness: 19/21 tasks (90%). 2 P2 tasks require ECharts reports.**
