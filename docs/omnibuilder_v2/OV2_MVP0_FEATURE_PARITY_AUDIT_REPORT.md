# OV2-MVP.0 — OMNIVIEW V2 FEATURE PARITY AUDIT REPORT

> **Fase:** OV2-MVP.0 — Omniview V2 Feature Parity Audit
> **Motor:** Control Foundation
> **Fecha:** 2026-06-12
> **Contexto:** Omniview V1 productivo activo. Omniview V2 en shadow/dev.
> **Clasificación:** `OV2_MVP_READY_WITH_GAPS`

---

## 1. EXECUTIVE SUMMARY

Omniview V2 tiene una arquitectura superior a V1 (modular, source-agnostic, snapshot-first, mejor governance) pero **faltan 22 features (33% de paridad) para ser MVP operativo.** De estos, **10 son P0** (bloquean uso diario), **10 son P1** (afectan operación pero no bloquean), y **8 son P2** (mejoras UX).

**Recomendación: Abrir OV2-MVP.1 Gap Closure P0 inmediatamente. V2 puede ser MVP en 1-2 semanas si se cierran los P0.**

---

## 2. GOVERNANCE VALIDATION

| Rule | Status |
|------|--------|
| No modificar UI | **PASS** — Audit only, zero code changes |
| No cambiar rutas productivas | **PASS** — V1 routes untouched |
| No apagar V1 | **PASS** — V2 shadow only |
| No promover Yango a fuente productiva | **PASS** — Source promotion still BLOCKED |
| No cambiar serving facts productivos | **PASS** — No DB writes |
| No abrir nuevos engines | **PASS** — Diagnostic/Forecast/Suggestion/Decision/Action remain BLOCKED |

---

## 3. V1 vs V2 ARCHITECTURE COMPARISON

| Dimension | Omniview V1 (Production) | Omniview V2 (Shadow) |
|-----------|--------------------------|----------------------|
| **File structure** | Flat `src/components/` + `omniview/` subdir | Modular `src/pages/omniview-v2-shadow/` with `components/`, `hooks/`, `design/`, `adapters/` |
| **Core matrix** | `BusinessSliceOmniviewMatrix.jsx` (4,072 lines) | `MatrixShell.jsx` + `MatrixRow.jsx` + `MatrixCell.jsx` (modular) |
| **Data flow** | Direct API calls in component | Custom hooks (`useOmniviewV2Shell`, `useOmniviewV2Matrix`) |
| **API endpoints** | `/ops/business-slice/*` (47+ endpoints) | `/ops/omniview-v2/*` (18 endpoints) |
| **Source systems** | Single (implicit CT) | Multi-source (CT_TRIPS_2026, YANGO_API_RAW) |
| **Cell inspector** | 904-line panel (Evolution + Momentum drill) | 156-line drawer (Value, Source, Trust, Lineage, Drill) |
| **Design system** | Tailwind + `ct-design-tokens.css` | Tailwind + own `MatrixVisualSystem.css` + `omniviewV2Tokens.js` |
| **KPIs** | 7 (commission, trips, avg_ticket, drivers, revenue, cancel_rate, trips_per_driver) | 5 (orders, drivers, revenue, avg_ticket, trips_per_driver) |
| **Serving** | Direct DB queries | Snapshot-first with runtime fallback |
| **Governance** | Freshness chain, trust badges, coverage % | Source badge, coverage badge, freshness badge, cell audit |
| **Status** | Production, ACTIVE in nav registry | DEV only, not in nav registry |

---

## 4. FEATURE PARITY SUMMARY

### 4.1 By Category

| Category | PARITY | PARTIAL | MISSING | BETTER_THAN_V1 | Total |
|----------|--------|---------|---------|----------------|-------|
| KPIs | 5 | 0 | 2 | 1 | 9 |
| Views/Modes | 4 | 1 | 7 | 2 | 14 |
| Filters | 4 | 0 | 5 | 1 | 10 |
| UX | 3 | 4 | 7 | 1 | 17 |
| Governance | 1 | 1 | 0 | 5 | 10 |
| Performance | 2 | 0 | 1 | 3 | 6 |
| **TOTAL** | **19 (29%)** | **6 (9%)** | **22 (33%)** | **13 (20%)** | **66** |

### 4.2 Parity Score

**29% full parity + 20% better-than-V1 = 49% net positive.** V2 is architecturally superior but feature-incomplete.

---

## 5. V2 STRENGTHS (Why this is worth finishing)

| # | Strength | Impact |
|---|----------|--------|
| 1 | **Modular architecture** — 1,300 lines vs V1's 7,000+ | Easier to maintain, test, extend |
| 2 | **Source-agnostic** — CT vs Yango toggle | Ready for source migration when CF-H2H opens |
| 3 | **Snapshot-first serving** — pre-built payloads | Lower DB load, faster responses |
| 4 | **Structured cell inspector** — Value, Source, Trust, Lineage, Drill sections | Better auditability than V1's monolithic panel |
| 5 | **Canonical source badges** — CANONICAL/SHADOW visible | Users know data provenance |
| 6 | **Cell auditability endpoint** — full lineage visibility | Debugging data issues is faster |
| 7 | **Cross-layer freshness observatory** — RAW → BRIDGE → SNAPSHOT | Multi-layer governance |
| 8 | **Fallback adapter pattern** — graceful degradation | Resilient to backend issues |
| 9 | **Separate data hooks** — `useOmniviewV2Shell`, `useOmniviewV2Matrix` | Reusable, testable logic |
| 10 | **Rich empty states** — NO_DATA, today-empty with guidance | Better UX than V1 |
| 11 | **Operating date endpoint** — smart date initialization | Reduces user configuration |
| 12 | **Reconciliation endpoints** — CT vs Yango comparison | Foundation for source trust |
| 13 | **Infra health + backend identity endpoints** | Operational visibility |

---

## 6. CRITICAL GAPS (P0 — 10 items)

| # | Gap | Impact |
|---|-----|--------|
| P0-1 | **Business Slice dimension missing** | Core V1 feature. V2 can't show KPI × slice grid. |
| P0-2 | **Signal colors missing** | No green/amber/red for operational decisions. |
| P0-3 | **City + Country filters** | Can't filter by basic operational dimensions. |
| P0-4 | **Business Slice filter** | Can't filter by slice. |
| P0-5 | **Commission rate KPI** | Core business metric missing. |
| P0-6 | **Double-scroll not verified** | Critical UX bug from early V1. |
| P0-7 | **Operational status bar** | No at-a-glance freshness/coverage/trust. |
| P0-8 | **KPI delta arrows** | No direction indicator on changes. |
| P0-9 | **Not in nav registry** | Can't navigate to V2. |
| P0-10 | **Cell inspector lacks Evolution drill** | Inspector less useful than V1. |

---

## 7. RISKS

| Risk | Severity | Mitigation |
|------|----------|------------|
| V2 becomes permanent "shadow" (never reaches production) | HIGH | Set hard deadline: MVP.4 must complete within 11 weeks |
| P0 closure introduces regressions in V1 | MEDIUM | V1 and V2 use separate endpoints and routes — no shared code paths |
| Business Slice dimension multiplies matrix complexity | MEDIUM | Start with top-5 slices only, expand gradually |
| Source promotion (Yango) still BLOCKED | LOW | V2's source-agnostic design means it works with CT data now, Yango later |
| Snapshot table unbounded growth | LOW | Add auto-expiry in MVP.2 (P2-8) |
| Operations team won't adopt V2 | MEDIUM | MVP.3 includes mandatory trial period with feedback collection |

---

## 8. RECOMMENDATION

### GO for OV2-MVP.1 Gap Closure P0

**OV2_MVP_READY_WITH_GAPS** — V2 is architecturally ready but feature-incomplete. The path to MVP is clear: close 10 P0 gaps (1-2 weeks), then harden UX (2-3 weeks). V2 can be a daily operational tool before source promotion opens.

### Prerequisites for OV2-MVP.1

1. Approve backlog: 10 P0 items prioritized
2. Allocate dev capacity: ~15-20 story points
3. Set target: V2 matrix showing business_slice dimension with signal colors, filters, and operational status bar

### Recommended parallel work

- **CF-H2E.2A** (Rate Limit & Throughput Governance) can run in parallel — no overlap with OV2-MVP.1
- **CF-H2H** (Source Promotion) MUST remain BLOCKED until OV2-MVP.4 (V1 Deprecation Readiness)

---

## 9. FILES CREATED

| File | Purpose |
|------|---------|
| `docs/omnibuilder_v2/OV2_MVP0_V1_INVENTORY.md` | V1 complete inventory (10 routes, 30+ components, 47+ endpoints) |
| `docs/omnibuilder_v2/OV2_MVP0_V2_INVENTORY.md` | V2 complete inventory (2 routes, 30+ components, 18+ endpoints) |
| `docs/omnibuilder_v2/OV2_MVP0_FEATURE_PARITY_MATRIX.md` | 66-item parity matrix with severity + recommendations |
| `docs/omnibuilder_v2/OV2_MVP0_GAP_BACKLOG.md` | Prioritized backlog: 10 P0, 10 P1, 8 P2, 8 P3 |
| `docs/omnibuilder_v2/OV2_MVP0_MVP_ROADMAP.md` | 4-phase roadmap: P0 → UX → Acceptance → Deprecation |
| `docs/omnibuilder_v2/OV2_MVP0_FEATURE_PARITY_AUDIT_REPORT.md` | This report |

---

## 10. BACKLOG UPDATED

| Estado | Fase | Descripción |
|--------|------|-------------|
| **ACTIVE** | **OV2-MVP.0** | Feature Parity Audit (this document) |
| READY NEXT | **OV2-MVP.1** | Gap Closure P0 |
| BACKGROUND | CF-H2E.2A | Rate Limit & Throughput Governance |
| BACKGROUND | CF-H2E.3 | Continuous Multipark Shadow |
| BLOCKED | CF-H2H | Omniview Source Promotion |
| PENDING | OV2-MVP.2 | UX Hardening |
| PENDING | OV2-MVP.3 | Operational Acceptance |
| PENDING | OV2-MVP.4 | V1 Deprecation Readiness |

---

## 11. ANSWER TO EXPLICIT QUESTION

**¿Estamos listos para abrir OV2-MVP.1 Gap Closure P0?**

**Sí — GO.**

La auditoría de paridad está completa:
- V1 inventariado: 47 endpoints, 30+ componentes, 7 KPIs, 9 filtros, 7 vistas
- V2 inventariado: 18 endpoints, 30+ componentes, 5 KPIs, 6 filtros, 4 vistas
- Matriz de paridad: 66 items evaluados (29% parity, 33% missing)
- 10 gaps P0 identificados y priorizados
- Roadmap definido: 4 fases, 7-11 semanas estimadas
- V1 productivo intacto, V2 shadow sin tocar

OV2-MVP.1 tiene scope claro (10 P0), criterios GO medibles, y no interfiere con CF-H2E.2A ni con Omniview productivo.

---

## 12. FIRMA

| Campo | Valor |
|-------|-------|
| **Auditado por** | OV2-MVP.0 Feature Parity Audit |
| **Fecha** | 2026-06-12 |
| **Motor** | Control Foundation |
| **Clasificación** | `OV2_MVP_READY_WITH_GAPS` |
| **Veredicto** | **GO for OV2-MVP.1 Gap Closure P0** |
| **Próxima fase** | OV2-MVP.1 — cerrar 10 gaps P0 (1-2 semanas) |
