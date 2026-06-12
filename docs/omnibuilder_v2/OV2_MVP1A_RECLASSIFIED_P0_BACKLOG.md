# OV2-MVP.1A — RECLASSIFIED P0 BACKLOG

> **Fase:** OV2-MVP.1A — Core Parity Foundation
> **Fecha:** 2026-06-12
> **Principio:** NO Projection Mode separado. Execution context integrado.

---

## P0 — CORE PARITY (MVP blocker)

| # | Gap | Area | Principle |
|---|-----|------|-----------|
| P0-1 | **Business Slice dimension** | Backend + Frontend | Matrix must group rows by business_slice |
| P0-2 | **Business Slice filter** | Frontend + Backend | Filter matrix by slice |
| P0-3 | **City filter** | Frontend + Backend | Filter by city |
| P0-4 | **Country filter** | Frontend + Backend | Filter by country |
| P0-5 | **Commission KPI** | Backend + Frontend | commission_pct in selector + executive state |
| P0-6 | **V2 route visible in nav as MVP/Shadow** | Config | Navigation registry entry |
| P0-7 | **Operational status bar** | Frontend | Collapsible bar: freshness, coverage, trust, health |
| P0-8 | **No double-scroll verification/fix** | Frontend | MatrixShell overflow audit |
| P0-9 | **Execution Context integrated** | Backend + Frontend | Real + Plan + Gap + Attainment% — no separate mode |

---

## MOVED OUT OF P0

| Old P0 | Reason | New Priority |
|--------|--------|-------------|
| Signal colors in matrix cells | Not core parity — UX signal layer | P1 (OV2-MVP.1B) |
| KPI delta arrows (direction) | Not core parity — UX signal layer | P1 (OV2-MVP.1B) |
| Cell inspector Evolution/Momentum drill | Not core parity — requires ECharts + trend data | P2 (OV2-MVP.2) |
| Projection Mode (separate) | **CANCELED** — Execution Context replaces it | — |
| Root cause engine | Diagnostic Engine — NOT Control Foundation | BACKLOG |
| Momentum drill chart | ECharts — requires separate data pipelines | P2 (OV2-MVP.2) |
| ECharts reports | Separate view — not MVP blocker | P2 (OV2-MVP.2) |
| Zoom control | UX enhancement | P3 |
| Fullscreen toggle | UX enhancement | P3 |
| Backfill controls | Dev-ops concern | P3 |

---

## EXECUTION CONTEXT MODEL (replaces Projection Mode)

```
For each KPI/grain/slice:
  real_value     — always present (from serving facts)
  plan_value     — present if plan exists
  gap_value      — plan - real (if plan exists)
  attainment_pct — real / plan * 100 (if plan exists)
  plan_status    — AVAILABLE | MISSING | NOT_APPLICABLE
```

**Rules:**
- Real ALWAYS visible. Never hidden if plan missing.
- Plan shown side-by-side (not toggle, not separate screen).
- Gap and Attainment% are derived, not separate KPIs.
- If plan missing: show `Plan: —` with badge "Plan no disponible".
- No root cause. No forecast. No expected progress.

---

## COMMISSION KPI DEFINITION

```
Source CT:     commission_pct from ops.real_business_slice_*_fact
Source Yango:  commission_rate = revenue_yego / GMV (if GMV > 0)

Badge: CT_BRIDGE | YANGO_API | NOT_AVAILABLE
Unit: % (0-100)
Format: 2 decimals
```

---

## STATUS BAR MODEL

```
Collapsible bar showing:
  - Operating date: latest_closed_date
  - Freshness: FRESH (<=1d) | STALE (1-3d) | CRITICAL (>3d)
  - Coverage: % from day_fact
  - Trust: OK | WARNING based on freshness + coverage
  - Source: CT_TRIPS_2026 / YANGO_API_RAW + canonical_ready
  - Fallback: used / not used
  - Backend identity: git hash (last 7 chars)
  - Health: DB available + pool status

Consumes existing endpoints:
  - /ops/omniview-v2/health
  - /ops/omniview-v2/freshness-observatory  
  - /ops/omniview-v2/backend-identity
  - /ops/omniview-v2/shell (for coverage)
```

---

## VERIFICATION CRITERIA

- [ ] V2 shows business_slice rows in matrix
- [ ] Country/City/B.Slice filters work in CommandHeader
- [ ] Commission KPI visible in selector + executive state
- [ ] Execution context shows Real + Plan/Gap/Attainment in same cell/row
- [ ] Missing plan does NOT hide Real
- [ ] Status bar visible, collapsible, shows all metrics
- [ ] V2 route navigable from Operacion tab as "Omniview V2 MVP"
- [ ] No double-scroll on matrix
- [ ] V1 unchanged
- [ ] 0 secrets exposed
