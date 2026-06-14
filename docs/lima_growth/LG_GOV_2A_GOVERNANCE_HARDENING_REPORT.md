# LG_GOV_2A_GOVERNANCE_HARDENING_REPORT

**Phase:** LG-CF-GOV-2A — Governance Hardening  
**Generated:** 2026-06-12  
**Predecessor:** LG-CF-RECOVERY-1B (Reality Reconciliation: Operativamente sana, mal gobernada)  
**Veredict:** `Control Foundation — OPERATIVAMENTE SANA. GOBERNANZA DEGRADADA. Cierre condicional posible en LG-CF-RECOVERY-2.`

---

## 1. EXECUTIVE SUMMARY

Control Foundation de Lima Growth está **operativamente sana**: 9 de 10 tablas auditadas tienen datos frescos (2026-06-12). Los 7 tabs del Intelligence Dashboard muestran datos reales. Los endpoints responden 200.

Sin embargo, la **gobernanza está degradada**: solo el 31% de las tablas tienen escritores automatizados en `autonomous_tick`. Dos tablas son huérfanas (sin escritor versionado). Cuatro escritores requieren activación manual. El pipeline V2 funciona pero solo bajo trigger manual. El health endpoint reporta CRITICAL por violaciones de SLA, no por ausencia de datos.

**La deuda de gobernanza no impide la operación, pero sí impide declarar Control Foundation como cerrada.**

---

## 2. REGISTRIES GENERATED

| Registry | File | Content |
|----------|------|---------|
| Writer Registry | `LG_GOV_2A_WRITER_REGISTRY.md` | 42 tables with writer function, file, trigger, scheduler, frequency, owner |
| Scheduler Registry | `LG_GOV_2A_SCHEDULER_REGISTRY.md` | 4 schedulers: autonomous_tick, V2 cron, manual POST endpoints, scripts |
| Orphan Registry | `LG_GOV_2A_ORPHAN_REGISTRY.md` | 5 UNGOVERNED, 2 LEGACY, 1 DEPRECATED, 1 NOT DEPLOYED |
| Health Contract V2 | `LG_GOV_2A_HEALTH_CONTRACT_V2.md` | DATA HEALTH vs SLA HEALTH specification with endpoints |
| Explorer Readiness | `LG_GOV_2A_DRIVER_EXPLORER_READINESS.md` | NO-GO. 3/10 criteria fail. Deployment sequence defined. |

---

## 3. RISK MATRIX

### CRITICAL Risks

| # | Risk | Impact | Probability | Mitigation |
|---|------|--------|-------------|------------|
| R1 | V2 pipeline cron fails silently (already happening) | Intelligence layer freezes when manual triggers stop | **HIGH** (already occurred for 06-11/12 until manual intervention) | Integrate V2 pipeline into autonomous_tick cascade |
| R2 | Orphan tables (`v2_taxonomy_daily`, `driver_movement_fact`) have NO writer | Tables freeze permanently if external process stops | **HIGH** (inevitable without governance) | Create versioned writers. Integrate into cascade. |

### HIGH Risks

| # | Risk | Impact | Probability | Mitigation |
|---|------|--------|-------------|------------|
| R3 | `rna_priority_fact` only populated manually (LG-RNA-1B one-time recovery) | RNA scoring becomes stale | **MEDIUM** (table has no date column — single snapshot) | Add to autonomous_tick or V2 pipeline |
| R4 | `program_effectiveness_fact` only populated manually (LG-IMP-1C one-time recovery) | Effectiveness tab shows stale data | **MEDIUM** (34 rows, last updated 06-12) | Add to V2 pipeline step 9 |
| R5 | `driver_explorer_fact` not created (migration 220 not applied) | Explorer UI cannot use canonical endpoint | **HIGH** (table doesn't exist) | Apply migration. Activate writer. |
| R6 | Health endpoint CRITICAL status normalized by operators | True CRITICAL events ignored | **MEDIUM** (cry-wolf effect) | Implement DATA HEALTH vs SLA HEALTH separation |

### MEDIUM Risks

| # | Risk | Impact | Probability | Mitigation |
|---|------|--------|-------------|------------|
| R7 | `data_quality = COMPLETE` reported when sources are stale (checks table existence, not rows) | False confidence in data completeness | **HIGH** (current behavior) | Fix contract to check row counts per target_date |
| R8 | `operational-date` reports `is_fresh: true` without checking intelligence tables | System thinks it's caught up when it's not | **MEDIUM** (led to 2-day gap in LG-CF-RECOVERY-1) | Extend freshness check to lifecycle/taxonomy/movement |
| R9 | `loopcontrol_result_sync` near-empty (10 rows) | Contact fields always NULL in Explorer | **LOW** (design accepts NULL) | Populate via LoopControl export pipeline |

---

## 4. REMAINING DEBT

### Governance Debt

| # | Debt Item | Tables Affected | Resolution |
|---|-----------|----------------|------------|
| D1 | V2 pipeline not in autonomous_tick | 9 shadow tables | Add `run_lima_growth_v2_daily_pipeline()` call to autonomous_tick cascade |
| D2 | Orphan writers (no versioned code) | `v2_taxonomy_daily`, `driver_movement_fact` | Create `build_taxonomy_v2_daily()` and `build_movement_fact()` in versioned services |
| D3 | Manual-only writers | lifecycle_daily, rna_priority_fact, program_effectiveness_fact, explorer_fact | Integrate into cascade or cron |
| D4 | `data_quality` contract (table existence vs row counts) | `driver_explorer_fact` | Fix `build_driver_explorer_fact()` quality check |
| D5 | Health monitoring SLA-only (no DATA HEALTH signal) | `/growth/health` | Implement V2 contract (separate DATA HEALTH + SLA HEALTH) |
| D6 | Freshness check ignores intelligence layer | `detect_latest_closed_data_date()` | Add lifecycle/taxonomy/movement to freshness detection |

### Technical Debt

| # | Debt Item | Files | Resolution |
|---|-----------|-------|------------|
| D7 | Migration 220 not applied | Alembic head | `alembic upgrade head` |
| D8 | `driver_explorer_fact` not populated | Serving fact chain | Run build script + enable feature flag |
| D9 | Legacy tables still read by consumers | `driver_taxonomy_daily`, `driver_segment_snapshot` | Migrate consumers to V2 sources, then deprecate |

---

## 5. CLOSURE CRITERIA FOR CONTROL FOUNDATION

### Minimum Viable Closure (MUST HAVE)

| # | Criterion | Current | Target |
|---|-----------|---------|--------|
| C1 | All 7 Intelligence Dashboard tabs show fresh data (≤1 day stale) | **PASS** (all tabs 06-12 data) | Already met |
| C2 | No orphan tables with active consumers | **FAIL** (2 orphans, 3 active consumers) | Replace with versioned writers |
| C3 | V2 pipeline integrated into autonomous_tick OR reliable cron | **FAIL** (manual trigger only) | Automated daily execution |
| C4 | `data_quality` reflects actual row freshness | **FAIL** (checks table existence) | Check row counts per target_date |
| C5 | `driver_explorer_fact` populated and serving UI | **FAIL** (table doesn't exist) | Apply migration + build + enable |
| C6 | Health endpoint returns HEALTHY or DEGRADED (not CRITICAL) when data is fresh | **FAIL** (CRITICAL from SLA lag) | Implement DATA HEALTH signal |
| C7 | 0 false-positive freshness signals | **FAIL** (`operational-date` ignores intelligence layer) | Extend freshness detection |

### Full Closure (SHOULD HAVE)

| # | Criterion | Current | Target |
|---|-----------|---------|--------|
| C8 | All writers versioned and in repository | **FAIL** (2 external) | 100% versioned |
| C9 | All writers integrated into automated scheduler | **FAIL** (57% manual) | ≥80% automated |
| C10 | 90-day retention pruning active | **NOT IMPLEMENTED** | Weekly DELETE |
| C11 | Legacy tables fully deprecated (no consumers) | **FAIL** (2 legacy tables read) | Migrate consumers, drop tables |
| C12 | DATA HEALTH + SLA HEALTH endpoints live | **NOT IMPLEMENTED** | Implement V2 contract |

---

## 6. PATH TO CLOSURE

### Phase LG-CF-RECOVERY-2 (Minimum Viable Closure)

| Step | Action | Criteria Met |
|------|--------|-------------|
| 1 | Create versioned writer for `v2_taxonomy_daily` | C2 |
| 2 | Replace `driver_movement_fact` consumer paths with `v2_movement_fact` | C2 |
| 3 | Add V2 pipeline call to autonomous_tick cascade (feature-flagged) | C3 |
| 4 | Fix `data_quality` in `build_driver_explorer_fact()` | C4 |
| 5 | Apply migrations 219 + 220, build first explorer fact, enable feature flag | C5 |
| 6 | Implement DATA HEALTH endpoint (read-only, additive) | C6 |
| 7 | Extend `detect_latest_closed_data_date()` to intelligence tables | C7 |

### Phase LG-CF-RECOVERY-3 (Full Closure)

| Step | Action | Criteria Met |
|------|--------|-------------|
| 8 | Integrate `build_rna_priority()` into weekly scheduler | C9 |
| 9 | Integrate `build_program_effectiveness` into V2 pipeline | C9 |
| 10 | Implement 90-day pruning in explorer fact writer | C10 |
| 11 | Migrate Segments tab from `driver_taxonomy_daily` to `v2_taxonomy_daily` | C11 |
| 12 | Deprecate `driver_segment_snapshot` | C11 |
| 13 | Implement full SYSTEM HEALTH endpoint | C12 |

---

## 7. FINAL VERDICT

### Today (2026-06-12)

**Control Foundation está OPERATIVAMENTE SANA.** Los datos existen. Los tabs funcionan. Los endpoints responden. La máquina de crecimiento produce valor operacional.

**Control Foundation NO está GOBERNADA.** Los escritores son externos o manuales. Los schedulers fallan silenciosamente. El health monitoring genera falsas alarmas. La serving fact canónica del Explorer no existe en producción.

### Condición para cierre

**Control Foundation puede declararse cerrada cuando LG-CF-RECOVERY-2 complete los criterios C1-C7.** Esto representa el cierre mínimo viable: todas las tablas tienen escritores versionados automatizados, el health monitoring es honesto, y la serving fact del Explorer está viva.

### Estimación de esfuerzo

| Phase | Steps | New Files | Modified Files | Risk |
|-------|-------|-----------|---------------|------|
| LG-CF-RECOVERY-2 | 7 steps | ~3 services + 1 migration | ~3 existing | Medium |
| LG-CF-RECOVERY-3 | 6 steps | ~2 endpoints | ~4 existing | Low |

### Veredicto Final

**LG_GOV_2A_COMPLETE — La gobernanza está documentada. La deuda está cuantificada. El camino al cierre está definido. Proceder a LG-CF-RECOVERY-2 para cerrar los gaps de gobernanza y alcanzar el cierre mínimo viable de Control Foundation.**
