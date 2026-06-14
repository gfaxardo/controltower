# LG_CF_RECOVERY_2A_REPORT

**Phase:** LG-CF-RECOVERY-2A — Control Foundation Closure  
**Generated:** 2026-06-12  
**Predecessors:**
- LG-CF-RECOVERY-1 (Foundation Audit — NO-GO, 8/8 criteria fail)
- LG-CF-RECOVERY-1B (Reality Reconciliation — Operativamente sana, mal gobernada)
- LG-CF-GOV-2A (Governance Hardening — 6 registries + contracts)  
**Veredict:** `Control Foundation — 8% cerrada. Se requieren 2 fases más para cierre mínimo viable.`

---

## 1. THE QUESTION

**¿Cuánto falta realmente para declarar CONTROL FOUNDATION CLOSED?**

---

## 2. THE ANSWER

**Falta LG-CF-RECOVERY-2 (7 steps, ~3 new files, ~5 modified files) para alcanzar el cierre mínimo viable (C1-C7, 58%).**

**Falta LG-CF-RECOVERY-3 (5 steps adicionales) para alcanzar el cierre completo (C1-C12, 100%).**

---

## 3. CURRENT STATE: 8% CLOSED

| Tier | Score | What's Closed |
|------|-------|--------------|
| Minimum Viable (C1-C7) | 1/7 (14%) | C1: All 7 tabs show fresh 06-12 data |
| Full Closure (C8-C12) | 0/5 (0%) | Nothing |
| **Combined** | **1/12 (8%)** | |

### Why Only 8%

| Passes | Fails | Root Cause |
|--------|-------|------------|
| C1 | — | Data IS fresh (confirmed by real DB audit) |
| — | C2 | 2 orphan tables without versioned writers |
| — | C3 | V2 pipeline not automated (manual trigger only) |
| — | C4 | `data_quality` checks table existence, not row counts |
| — | C5 | `driver_explorer_fact` not created (migration 220 not applied) |
| — | C6 | Health endpoint returns CRITICAL despite fresh data |
| — | C7 | False-positive freshness signals from operational-date API |
| — | C8-C12 | Full closure criteria not addressed |

---

## 4. WHAT HAS BEEN COMPLETED IN LG-CF-RECOVERY-2A

| Document | Content | Value |
|----------|---------|-------|
| `LG_EXP_DEPLOYMENT_PLAN.md` | 7-step deployment sequence with pre-flight checks, rollback, and validation | Ready-to-execute runbook for driver_explorer_fact deployment |
| `LG_DRY_RUN_FIRST_BUILD.md` | Simulated first build: 18,545 rows, 9 JOINs, 30-60s, ~33 MB, GO verdict | Risk assessment complete. No blockers found. |
| `LG_HEALTH_V2_RECONCILIATION.md` | 4 health signals compared. 7/11 contradictions found. DATA HEALTH vs SLA HEALTH architecture designed. | Correct health signal identified: DEGRADED (not CRITICAL, not HEALTHY). |
| `LG_WRITER_OWNERSHIP_MATRIX.md` | 34 writers classified P0/P1/P2. All 4 P0 are automated. Governance gap is in P1. | Operational foundation is solid. Risk is limited to Intelligence tabs. |
| `LG_CF_CLOSURE_SCORECARD.md` | C1-C12 scored with real evidence. 1/12 passed (8%). Gap analysis complete. | Quantified distance to closure. Two-phase roadmap defined. |

---

## 5. THE GAP IN ONE SENTENCE

**All P0 writers (operational layer) are automated and healthy. All P1 writers (intelligence layer) are manual or external. 11 of 12 closure criteria are blocked by the P1 governance gap.**

---

## 6. PATH TO MINIMUM VIABLE CLOSURE (LG-CF-RECOVERY-2)

| Step | Action | Criteria Closed | New/Modified Files |
|------|--------|----------------|-------------------|
| 1 | Create `build_taxonomy_v2_daily()` versioned writer for orphan table | C2 | 1 new service |
| 2 | Migrate `driver_movement_fact` consumers to `v2_movement_fact` + derive fallback | C2 | 1 modified service |
| 3 | Add `run_lima_growth_v2_daily_pipeline()` call to autonomous_tick (feature-flagged) | C3 | 5 lines in scheduler |
| 4 | Fix `data_quality` to check `COUNT(*) WHERE date = target_date` | C4 | 10 lines in explorer writer |
| 5 | Apply migrations 219+220, run first build, enable feature flag | C5 | 2 ops commands |
| 6 | Implement `GET /growth/data-health` (COUNT per table per date) | C6, C7 | 1 new service + endpoint |
| 7 | Extend `detect_latest_closed_data_date()` to check intelligence tables | C7 | 5 lines in refresh service |

**After LG-CF-RECOVERY-2: All minimum viable criteria (C1-C7) = PASS. Closure = 58%.**

---

## 7. PATH TO FULL CLOSURE (LG-CF-RECOVERY-3)

| Step | Action | Criteria Closed | Notes |
|------|--------|----------------|-------|
| 8 | Create versioned `build_movement_fact()` writer for production table | C8, C9 | Replace V2 shadow table dependency |
| 9 | Integrate RNA + effectiveness + explorer writers into weekly scheduler | C9 | 3 more writers automated |
| 10 | Implement 90-day DELETE pruning per growth table | C10 | Maintenance script |
| 11 | Migrate Segments tab + actionable lists to V2 sources. Drop legacy tables. | C11 | 2 modified services |
| 12 | Implement SLA HEALTH + SYSTEM HEALTH endpoints | C12 | 2 new endpoints |

**After LG-CF-RECOVERY-3: All criteria (C1-C12) = PASS. Closure = 100%.**

---

## 8. RISK ASSESSMENT FOR CLOSURE

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| V2 pipeline integration breaks autonomous_tick | LOW | HIGH | Feature flag + gradual rollout (1 day shadow, then enable) |
| Orphan table replacement breaks consumers | MEDIUM | MEDIUM | Run shadow writes for 1 week before switching consumers |
| data_quality fix reveals worse state than expected | LOW | LOW | Read-only change; just makes existing degradation visible |
| Migration 217 conflict (table already exists) | LOW | LOW | CREATE TABLE IF NOT EXISTS is idempotent |
| First build times out | LOW | MEDIUM | Increase TIMEOUT_MS to 120s; run during low-traffic window |

---

## 9. HONEST ASSESSMENT

### What Control Foundation Does Well

- **Ingests raw data** from Yango API every 5 minutes (autonomous_tick)
- **Builds operational snapshots** (driver_state, program_eligibility) automatically
- **Generates serving facts** for Overview, Programs, Queue, Action Plan every 5 minutes
- **All 7 Intelligence Dashboard tabs show real data** (06-12 confirmed)
- **V2 pipeline runs successfully** when triggered (17/17 manual runs = SUCCESS)
- **Complete phase documentation** (PERF-1A, EXP-1B/1C/1D/1E, CF-RECOVERY-1/1B, GOV-2A)
- **Driver Explorer canonical contract and code ready** (waiting for migration 220)

### What Control Foundation Does NOT Do Well

- **V2 pipeline not automated** (failing cron, no autonomous_tick integration)
- **2 orphan tables** (populated externally, no versioned writer)
- **57% of writers require manual trigger**
- **Health monitoring misleading** (CRITICAL when data is fresh, HEALTHY when data is stale)
- **data_quality reports false COMPLETE** (checks table existence, not row freshness)
- **driver_explorer_fact not deployed** (table doesn't exist in production)
- **No retention pruning** (tables grow indefinitely)

---

## 10. FINAL VERDICT

### Today

**Control Foundation está en 8% de cierre.** La base operacional es sólida (snapshot + eligibility automatizados). La capa de inteligencia está funcional pero no gobernada (V2 pipeline manual, tablas huérfanas). El Explorer canónico está diseñado y codificado pero no desplegado.

### Próximo paso inmediato

**LG-CF-RECOVERY-2** — 7 pasos para alcanzar el cierre mínimo viable. Estimación: ~3 nuevos archivos backend, ~5 archivos modificados, 2 comandos de operaciones. Sin riesgo para el runtime crítico (autonomous_tick no se modifica, solo se extiende con feature flag).

### Meta final

**Control Foundation se considera cerrada cuando:**
1. Todas las tablas tienen escritores versionados automatizados
2. La serving fact del Explorer está viva y sirviendo al UI
3. El health monitoring es honesto (DATA HEALTH ≠ SLA HEALTH)
4. No hay señales de frescura falsas
5. El 80%+ de los escritores están integrados en schedulers

**Eso requiere LG-CF-RECOVERY-2 + LG-CF-RECOVERY-3.**
