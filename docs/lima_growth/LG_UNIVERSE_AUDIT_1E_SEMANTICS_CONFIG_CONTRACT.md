# LG-UNIVERSE-AUDIT-1E — Universe Semantics + Config Contract Audit

**Date:** 2026-06-14
**Phase:** LG-UNIVERSE-AUDIT-1E (Semantics Audit)
**Mode:** AUDIT + DESIGN — No implementation
**Status:** CONFIG_CONTRACT_READY

---

## 1. Executive Decision

### LG_UNIVERSE_AUDIT_1E_CONFIG_CONTRACT_READY

Current 9-universe classification is operational but hardcoded. This audit defines the path toward a versioned, simulatable, auditable Universe Configuration V2. 6 proposed tables, simulation flow, and backlog phases defined. 0 code changes.

---

## 2. Current Universe Snapshot (2026-06-15)

| Universe | Drivers | Export | Avg Wk | Avg Inact | Avg Gap | Avg Age |
|----------|---------|--------|--------|-----------|---------|---------|
| Cemetery | 12,403 | 0 | 7.5 | 236.1 | — | 272d |
| Recovery Low | 2,989 | 2,989 | 4.2 | 31.3 | 1.0 | 136d |
| Active Growth | 1,652 | 1,652 | 19.8 | 2.9 | 7.6 | 248d |
| Recovery High | 877 | 877 | 14.4 | 28.7 | 1.0 | 247d |
| Consolidation | 344 | 344 | 17.4 | 2.9 | 82.6 | 67d |
| Ramp Up | 204 | 204 | 15.1 | 3.1 | 84.9 | 29d |
| New | 48 | 48 | 9.5 | 3.3 | 35.3 | 12d |
| Protected | 28 | 0 | 73.1 | 2.2 | 0 | 125d |

---

## 3. Sample Review Findings

**New (48 drivers):** Age 10-14 days, trips <50. Correctly classified. Low activity (avg 9.5 wk).

**Ramp Up (204 drivers):** Age 15-45d. One driver has 30d=312 but wk=23 — was very active, now dropping. Large gap to 100/wk (84.9 avg). These drivers need significant improvement.

**Consolidation (344 drivers):** Age 46-90d. Gap of 82.6 to 100/wk. Need sustained effort.

**Active Growth (1,652 drivers):**
- 795 in band 1-10 (near-zero weekly trips)
- Only 37 in band 76-99 (close to protected)
- Most AG drivers have minimal activity — effectiveness of "band growth" treatment is questionable

**Recovery High (877):** Average 28.7 days inactive. High value due to historical best_week. Should be worked first.

**Recovery Low (2,989):** Average 31.3 days inactive. Low value. Mass campaigns recommended.

**Protected (28):** Only 0.15% of fleet. The 100 trips/week target is very demanding for Lima. Consider lowering or adding intermediate "monitoring" states.

**Cemetery (12,403):** 236 days avg inactive. Genuinely churned. Excluded from daily ops. Correct.

---

## 4. Operator Universe Model (Designed)

| # | Universe | Trigger | Mission | Target | Exit |
|---|----------|---------|---------|--------|------|
| 1 | Nuevos | hire_date ≤14d AND trips <50 | Activar nuevos conductores | 50 viajes en ventana | 50 viajes OR >14d |
| 2 | Reactivados | Last reactivation ≤14d AND trips <50 | Reactivar conductores que volvieron | 50 viajes en nuevo ciclo | 50 viajes OR inactividad |
| 3 | Ramp Up | 15-45d desde ancla | Llevar a 100 viajes/semana | 100/wk | 100/wk OR >45d |
| 4 | Consolidation | 46-90d desde ancla | Sostener 100 viajes/semana | 100/wk | 100/wk OR >90d |
| 5 | Active Growth | 90+d, activo, <100/wk | Subir de banda de productividad | Siguiente banda | 100/wk OR banda subida |
| 6 | Protected/Top | 100+ viajes/semana | Monitorear, retener | Mantener | <100/wk OR inactividad |
| 7 | Recovery High | 7-60d inactivo, alto valor | Recuperar conductores valiosos | Reactivación | Actividad OR >60d |
| 8 | Recovery Low | 7-60d inactivo, bajo valor | Recuperación masiva | Reactivación | Actividad OR >60d |
| 9 | Cemetery | >60d inactivo | Separar de operación diaria | N/A | Reactivación |

---

## 5. Priority and Workload Audit

| Universe | Drivers | Suggested Channel | Est. Agents* |
|----------|---------|------------------|-------------|
| Recovery High | 877 | Agente humano | 18 (50/d) |
| New/Reactivados | 48 | Agente humano | 1 |
| Ramp Up | 204 | Agente humano | 4 |
| Consolidation | 344 | Agente humano | 7 |
| Active Growth | 1,652 | Call center / WhatsApp | 33 |
| Recovery Low | 2,989 | WhatsApp / SMS masivo | — |
| Cemetery | 12,403 | No trabajar | — |

*Estimado: 50 conductores/agente/día. Configurable.

---

## 6. Configuration Contract V2 (Proposed Tables)

### 6.1 `growth.universe_config_version`
Version tracking: DRAFT → SIMULATED → APPROVED → ACTIVE → RETIRED.

### 6.2 `growth.universe_definition_config`
Per-universe metadata: label, priority, actionable flag, export flag, channel, action category, target metric/value, exit condition.

### 6.3 `growth.universe_rule_config`
Per-universe rules: field_name, operator, value, priority, condition logic (AND/OR), null behavior.

### 6.4 `growth.universe_simulation_run`
Simulation metadata: version, source date, run time, status, counts, diff vs current.

### 6.5 `growth.universe_simulation_result`
Per-driver simulation results: current vs simulated universe, changed flag, reasons, evidence.

### 6.6 `growth.universe_config_activation_audit`
Activation audit: version, timestamp, previous version, rollback version, approval notes.

---

## 7. Simulation Flow

1. Create DRAFT config version
2. Simulate on latest worklist date
3. Compare: current vs simulated counts per universe, drivers moved, exportable delta
4. Review operational impact (agent workload, channel distribution)
5. Approve version → status ACTIVE
6. Writer reads ACTIVE version on next run
7. Rollback possible to previous version via activation audit

**Rules:** No activation without simulation PASS. No hot changes. Monday preferred for activation.

---

## 8. North Star Updates Required

| Document | Update |
|----------|--------|
| `LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md` | Section: Universe Configuration V2 — versioned, simulatable, auditable |
| `LG_NORTH_STAR_UI_OPERATIONAL_CONTRACT.md` | Section: Universe Config UI — simulation review, version management |
| `GROWTH_MACHINE_CANONICAL.md` | Section: Universe Config V2 tables + simulation flow |
| `ACTIVE_SCOPE_CONTRACT.md` | In-scope: configuration audit, simulation design. Not: implementation yet |
| `KNOWN_CONSTRAINTS.md` | Deferred: hardcoded rules until V2 config is implemented |

---

## 9. Backlog Created

| Phase | Name | Priority |
|-------|------|----------|
| LG-UNIVERSE-CONFIG-1F | Universe Config V2 Contract Finalization | P0 |
| LG-UNIVERSE-SIM-1G | Universe Rule Simulation Engine | P0 |
| LG-UNIVERSE-ACTIVATE-1H | Active Version Integration into Worklist Writer | P1 |
| LG-UNIVERSE-UI-1I | Universe Config UI / Simulation Review | P1 |

---

## 10. What Was Not Changed

0 code. 0 migrations. 0 rules. 0 thresholds. 0 backend. 0 frontend. 0 Control Loop.

---

## 11. Verdict

### LG_UNIVERSE_AUDIT_1E_CONFIG_CONTRACT_READY

Current classification audited. Operator model designed. 6 tables proposed. Simulation flow defined. 4 backlog phases created. North Star updates pending implementation.

---

*Config contract defined. Ready for Universe Config V2 implementation phases.*
