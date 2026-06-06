# LG-C1.4-P2 — UX Operational Audit

**Date:** 2026-06-05
**Phase:** LG-C1.4-P2 UX Operational Audit
**Auditor:** AI Governance Agent

---

## 1. Inventario de Tabs

| Tab | Visible | Renderiza | Datos | Acciones | Estado UX |
|-----|---------|-----------|-------|----------|-----------|
| Resumen | SI | OK | opSummary (real) | Ninguna | **PASS** |
| Estado del Conductor | SI | OK | driverState (real) | Ninguna | **PASS** |
| Programas | SI | OK | programsSummary (real) | Ninguna | **PASS** |
| Oportunidades | SI | OK | opportunities (legacy) | Ninguna | **PASS** |
| Ejecución Loop | SI | OK | exports + config | Ninguna | **PASS** |
| Impacto | SI | OK | N/A | Ninguna | **PASS** (P0: removidas métricas falsas) |
| Movimiento | SI | OK | N/A | Ninguna | **PASS** (P0: marcado "No certificada") |
| Atribución | SI | OK | N/A | Ninguna | **PASS** (P0: consolidado, no sub-cards falsas) |
| Worklist | SI | OK | worklist (real) | Filtros (funcionan) | **PASS** |
| Queue | SI | OK | queue (real) | Build Queue (funciona) | **PASS** |
| Configuración | SI | OK | opSummary + config + capacity | Save capacity (funciona) | **PASS** |

## 2. Matriz Funcionalidad → UX

| Funcionalidad | Backend | Frontend API | Tab | Estado |
|--------------|---------|-------------|-----|--------|
| Operational Summary | `/operational-summary` | `getLimaGrowthOperationalSummary` | Resumen + Config | VISIBLE_AND_WORKING |
| Driver State Summary | `/driver-state/summary` | `getLimaGrowthDriverStateSummary` | Estado del Conductor | VISIBLE_AND_WORKING |
| Programs Summary | `/programs/summary` (enriched) | `getLimaGrowthProgramsSummary` | Programas | VISIBLE_AND_WORKING |
| Opportunity Worklist | `/opportunity-worklist` | `getLimaGrowthOpportunityWorklist` | Worklist | VISIBLE_AND_WORKING |
| Priority Allocation | `/priority-allocation` | `getLimaGrowthPriorityAllocation` | Resumen | VISIBLE_AND_WORKING |
| Capacity Config | `/capacity/config` | `get/updateLimaGrowthCapacityConfig` | Configuración | VISIBLE_AND_WORKING |
| Channel Allocation | `/channel-allocation` | `getLimaGrowthChannelAllocation` | Resumen | VISIBLE_AND_WORKING |
| Assignment Queue | `/assignment-queue` | `build/getLimaGrowthAssignmentQueue` | Queue | VISIBLE_AND_WORKING |
| Queue Build | `/assignment-queue/build` | `buildLimaGrowthAssignmentQueue` | Queue | VISIBLE_AND_WORKING |
| Queue Export | `/assignment-queue/export` | N/A (no UI button) | Queue | BACKEND_ONLY |
| LoopControl Config | `/loopcontrol/config` | `getLoopControlConfig` | Configuración + Resumen | VISIBLE_AND_WORKING |
| LoopControl Export Ledger | `/loopcontrol/exports` | `getLoopControlExports` | Ejecución Loop | VISIBLE_AND_WORKING |
| Result Sync | `/loopcontrol/results/*` | N/A (no UI calls) | Impacto | BACKEND_ONLY |
| Impact | N/A (placeholder router) | N/A | Impacto | PLACEHOLDER |
| Movement | N/A (placeholder router) | N/A | Movimiento | PLACEHOLDER |
| Attribution | N/A (placeholder router) | N/A | Atribución | PLACEHOLDER |

## 3. User Journey Audit

| Paso | Puede hacerlo | Ve | Debería ver | Estado |
|------|--------------|-----|-------------|--------|
| 1. Entra a Lima Growth | SI | Resumen con pipeline | Pipeline operacional | **OK** |
| 2. Ve universo y pipeline | SI | Pipeline bar + KPIs | 18,475 → 5,777 → 500 | **OK** |
| 3. Revisa estado del conductor | SI | Lifecycle/Perf/Retention | Distribución real | **OK** |
| 4. Revisa programas | SI | 4 programas con conteos | Eligible/Prioritized/Actionable | **OK** |
| 5. Revisa oportunidades | SI | Tabla top 20 | Lista priorizada | **OK** |
| 6. Entra a Worklist | SI | Tabla con filtros | Worklist filtrable | **OK** |
| 7. Revisa Queue | SI | Tabla con filtros | Cola operativa | **OK** |
| 8. Construye Queue | SI | Botón "Construir cola" | Feedback de build | **OK** |
| 9. Exporta/Ve exportados | PARCIAL | Export ledger en Loop tab | Falta botón export en Queue | **WARNING** |
| 10. Verifica LoopControl LIVE | SI | Header + Config tab | LIVE mode, campaigns | **OK** |
| 11. Ve campañas ledger | SI | Tabla en Ejecución Loop | Historial de exports | **OK** |
| 12. Intenta ver resultados | NO | Impacto: "No certificada" | Vacío claro | **OK (P0)** |
| 13. Intenta ver impacto | NO | Impacto: "No certificada" | Vacío claro | **OK (P0)** |
| 14. Intenta ver movimiento | NO | Movimiento: "No certificada" | Vacío claro | **OK (P0)** |
| 15. Intenta ver atribución | NO | Atribución: "No certificada" | Vacío claro | **OK (P0)** |
| 16. Revisa configuración | SI | Policy + LC + Capacity | daily_action_capacity visible | **OK** |

## 4. API/UX Contract Validation

| Endpoint | Status | Shape Match | Loading | Empty | Error |
|----------|--------|-------------|---------|-------|-------|
| `/operational-summary` | 200 | OK | fetchSafely | opSummary=null → "—" | fetchSafely catch |
| `/driver-state/summary` | 200 | OK | fetchSafely | driverState=null → spinner | fetchSafely catch |
| `/programs/summary` | 200 | OK | fetchSafely | programsSummary=null → spinner | fetchSafely catch |
| `/assignment-queue` | 200 | OK | fetchSafely | Sin queue → mensaje | fetchSafely catch |
| `/loopcontrol/config` | 200 | OK | fetchSafely | config=null → "..." | fetchSafely catch |
| `/loopcontrol/exports` | 200 | OK | fetchSafely | Sin exports → EmptyState | fetchSafely catch |
| `/opportunity-worklist` | 200 | OK | fetchSafely | Sin worklist → spinner | fetchSafely catch |

## 5. Placeholders & Dead Tabs (P0 corregido)

| Tab | Antes | Después |
|-----|-------|---------|
| Impacto | Grid de 5 métricas con "—" (engañosa) | EmptyState único "No certificada" |
| Atribución | 3 sub-cards "Por Agente/Campaña/Iniciativa" | EmptyState consolidado "No certificada" |
| Movimiento | EmptyState con título vago | EmptyState "No certificada — Pendiente LC-2" |

## 6. P1/P2/P3 Backlog

**P1 — Funcionalidad importante no visible:**
- Botón "Exportar a LoopControl" en tab Queue (backlog: endpoint `/export` existe pero no tiene UI button)
- Result Sync: conectar UI al endpoint `/loopcontrol/results/*` cuando Miguel entregue API de resultados

**P2 — Mejora de claridad:**
- Unificar programas hardcodeados (STATIC_REGISTRY) en un solo source of truth
- Agregar "Exportar a LoopControl" como acción en Queue tab
- Mostrar `today` dinámico en vez de hardcodeado `2026-06-02`

**P3 — Estética:**
- Mejorar diseño de cards en tabs placeholder
- Agregar tooltips en métricas del pipeline

## 7. Build Result: **PASS** — 0 errores

## 8. Verdict

**PASS** — 11/11 tabs con estado correcto. P0 aplicados: tabs no certificadas ya no engañan al usuario. El usuario final puede operar sin ser engañado por la UX.
