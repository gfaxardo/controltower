# OV2-MVP.0 — MVP ROADMAP

> **Fase:** OV2-MVP.0 — Feature Parity Audit
> **Sub-document:** MVP Roadmap
> **Fecha:** 2026-06-12

---

## ROADMAP OVERVIEW

```
OV2-MVP.0  [CURRENT]  Feature Parity Audit
    ↓
OV2-MVP.1  [NEXT]     Gap Closure P0
    ↓
OV2-MVP.2             UX Hardening
    ↓
OV2-MVP.3             Operational Acceptance
    ↓
OV2-MVP.4             V1 Deprecation Readiness
```

---

## OV2-MVP.1 — GAP CLOSURE P0

### Objective

Cerrar los 10 gaps P0 que bloquean el uso diario de Omniview V2 como MVP operativo. Al final de esta fase, V2 debe ser **usable diariamente** para monitoreo operacional básico, aunque no reemplace a V1.

### Scope

| # | Gap P0 | Deliverable |
|---|--------|-------------|
| P0-9 | V2 route in nav registry | `operacion_omniview_v2` added to `controlTowerNavigationRegistry.js`, `productionReady: false`, visible in Operacion tab |
| P0-3 | City + Country filters | Backend: filter params in matrix/shell endpoints. Frontend: dropdowns in CommandHeader |
| P0-4 | Business Slice filter | Backend: business_slice filter param. Frontend: dropdown selector |
| P0-1 | Business Slice dimension | Backend: dimension column in MatrixResponse. Frontend: row grouping by slice |
| P0-5 | Commission rate KPI | Backend: commission_pct in matrix view model. Frontend: add to KPI selector + executive state |
| P0-2 | Signal colors in cells | Frontend: port insight thresholds, green/amber/red background on Cell rendered values |
| P0-8 | KPI delta arrows | Frontend: DeltaValue with ↑↓ and direction color |
| P0-7 | Operational status bar | Frontend: collapsible bar with freshness, coverage, period state, trust, KPI summary |
| P0-6 | No double-scroll fix | Frontend: verify MatrixShell overflow containment, add CSS fix if needed |
| P0-10 | Cell inspector Evolution drill | Frontend: current vs previous comparison section in CellInspector drawer |

### NOT doing

- No ECharts reports (P2-1)
- No full Projection mode (P1-6)
- No Momentum drill chart (P1-scope)
- No backfill controls (P2-5)
- No V1 deprecation
- No source promotion
- No Yango activation in production

### GO Criteria

- [ ] V2 route navigable from Operacion tab
- [ ] Business Slice dimension visible in matrix
- [ ] City + Country filters functional
- [ ] Business Slice filter functional
- [ ] Commission rate KPI visible
- [ ] Signal colors showing on cells
- [ ] KPI delta arrows showing direction
- [ ] Operational status bar visible + functional
- [ ] No double-scroll verified
- [ ] Cell inspector shows current vs previous comparison

### Expected Output

- Updated frontend: CommandHeader, MatrixShell, CellInspector, ExecutiveState
- Updated backend: matrix endpoint with filter params + business_slice dimension
- Navigation registry entry
- Visual QA: 5 screenshots of V2 matrix in different modes

---

## OV2-MVP.2 — UX HARDENING

### Objective

Cerrar gaps P1 para que V2 tenga paridad UX suficiente para uso operativo diario sin degradación frente a V1.

### Scope

| # | Gap P1 |
|---|--------|
| P1-1 | Plan vs Real daily + weekly grains |
| P1-2 | Cancel rate KPI |
| P1-3 | Subfleet filter |
| P1-4 | Sticky column headers |
| P1-5 | Virtual scroll / large dataset perf |
| P1-7 | Freshness governance chain visualization |
| P1-8 | Error boundary wrapper |
| P1-9 | Trust badges in matrix cells |
| P1-10 | Health state visualization |

### NOT doing

- No full Projection mode (deferred to OV2-MVP.3)
- No ECharts reports
- No new engines
- No source promotion

### GO Criteria

- [ ] PvR available at day/week grain with correct data
- [ ] Cancel rate visible + correct
- [ ] Subfleet toggle functional
- [ ] Column headers stick on scroll
- [ ] Matrix renders < 500ms for 100 slices × 7 KPIs × 30 days
- [ ] Freshness chain visible in UI
- [ ] Error boundary catches render errors
- [ ] Trust badges on cells
- [ ] Health endpoint data shown in status bar

### Expected Output

- Hardened V2 matrix: sticky headers, virtual scroll, trust badges
- PvR day/week endpoints + frontend toggle
- Freshness governance card (V2 design)
- Performance benchmark report

---

## OV2-MVP.3 — OPERATIONAL ACCEPTANCE

### Objective

V2 usado en paralelo con V1 por equipo de operaciones. Recolectar feedback, medir métricas de uso, cerrar gaps P2 restantes.

### Scope

| # | Gap P2 |
|---|--------|
| P2-1 | ECharts reports view |
| P2-4 | Park filter (multipark) |
| P2-7 | Executive banner |
| P2-8 | Snapshot auto-expiry |
| P1-6 | Full Projection mode (port from V1) |

### NOT doing

- No V1 deprecation
- No V1 shutdown
- No source promotion

### GO Criteria

- [ ] Operations team uses V2 ≥ 3 days/week
- [ ] < 5 critical bugs reported in 2-week trial
- [ ] Reports view functional with ECharts
- [ ] Park filter works with multipark data
- [ ] Projection mode shows plan vs real with root cause

### Expected Output

- Operations feedback log
- Bug tracker (tag: ov2-mvp3)
- Usage metrics (page views, time on page)
- Final feature parity score (target: >80%)

---

## OV2-MVP.4 — V1 DEPRECATION READINESS

### Objective

V2 alcanza paridad completa con V1. Plan de deprecación de V1 listo para ejecución.

### Scope

- Cerrar todos los gaps P2 + P3 restantes
- Auditar que 100% de queries de V1 tengan equivalente en V2
- Mapear rutas V1 → V2 para redirect
- Definir flag `V1_LEGACY_MODE` para rollback rápido
- Plan de comunicación a usuarios
- Dry-run de 1 semana con V1 oculto (flag ON) y V2 como default

### NOT doing

- No remover código V1 físicamente (solo ocultar)
- No eliminar endpoints V1

### GO Criteria

- [ ] 100% feature parity (0 MISSING en matriz)
- [ ] 1 semana de dry-run exitoso con V2 como default
- [ ] 0 rollbacks necesarios durante dry-run
- [ ] V1 flag documentado y testeado
- [ ] Equipo de operaciones aprueba transición

### Expected Output

- V1 deprecation runbook
- Redirect map (V1 route → V2 route)
- `V1_LEGACY_MODE` environment flag
- Dry-run certification report

---

## TIMELINE ESTIMATE

| Phase | Duration | Dependencies |
|-------|----------|-------------|
| OV2-MVP.0 | **CURRENT** | — |
| OV2-MVP.1 (Gap Closure P0) | 1-2 weeks | — |
| OV2-MVP.2 (UX Hardening) | 2-3 weeks | MVP.1 |
| OV2-MVP.3 (Operational Acceptance) | 2-3 weeks | MVP.2 |
| OV2-MVP.4 (V1 Deprecation) | 2-3 weeks | MVP.3 |
| **TOTAL** | **7-11 weeks** | |

---

## GATE RULES

1. **MVP.1 → MVP.2:** P0 gaps closed + GO criteria met
2. **MVP.2 → MVP.3:** P1 gaps closed + performance benchmark PASS
3. **MVP.3 → MVP.4:** Operations acceptance + <5 critical bugs
4. **MVP.4 → V1 Deprecation:** 100% parity + dry-run success (separate certification)

---

## BACKLOG TO MAINTAIN

| Estado | Fase |
|--------|------|
| ACTIVE | OV2-MVP.0 Feature Parity Audit |
| READY NEXT | OV2-MVP.1 Gap Closure P0 |
| PENDING | OV2-MVP.2 UX Hardening |
| PENDING | OV2-MVP.3 Operational Acceptance |
| PENDING | OV2-MVP.4 V1 Deprecation Readiness |
| BLOCKED | CF-H2H Omniview Source Promotion |
| BLOCKED | Diagnostic / Forecast / Suggestion / Decision / Action |
