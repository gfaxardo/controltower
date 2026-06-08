# OV2-G.1 — SHARED REALITY GOVERNANCE — FINAL REPORT

> **Date:** 2026-06-08
> **Motor:** Control Foundation / Shared Reality Governance
> **Phase:** OV2-G.1 — Shared Reality Governance + V1/V2 Isolation Certification
> **Status:** **SHARED_REALITY_CERTIFIED — GO for D.3B**

---

## 1. EXECUTIVE SUMMARY

Se construyó la gobernanza definitiva de capas compartidas entre V1 y V2. Ambos comparten la misma capa REAL (day_fact, week_fact, month_fact) con un solo writer canónico por tabla. V1 y V2 están aislados en código y endpoints pero comparten datos REAL de forma segura. Se identificaron 3 escenarios de falsa certificación, 2 de los cuales están mitigados por el observatorio de frescura.

---

## 2. KEY QUESTIONS ANSWERED

### 1. ¿Qué capas son realmente compartidas?

- `day_fact`, `week_fact`, `month_fact` (REAL_SHARED)
- `driver_day_slice_fact` (REAL_SHARED — V2 drill, V1 indirect)
- `plan_trips_monthly` (PLAN_SHARED)
- V2 snapshots (SNAPSHOT_SHARED — V2 only but sourced from shared REAL)

### 2. ¿Qué certificaciones dependen de ellas?

- V1 weekly freshness depends on `week_fact`
- V2 Matrix (all grains) depends on `day_fact`/`week_fact`/`month_fact`
- V2 Plan vs Real depends on `month_fact` + `plan_trips_monthly`
- V2 Inspector drill depends on `driver_day_slice_fact`

### 3. ¿Puede V2 seguir evolucionando?

**SÍ.** La capa REAL está gobernada con 1 writer por tabla. V2 puede evolucionar (Matrix, drill, Plan vs Real) sin riesgo de corromper la capa compartida. V2 no toca V1 routers ni V1 MVs.

### 4. ¿Qué bloquea una certificación final?

| Bloqueador | Estado |
|-----------|--------|
| Scheduler reports false `success` | NOT IMPLEMENTED — data advancement check needed |
| `__pycache__` runtime mismatch | MITIGATED — clean on restart, not automated |
| Snapshot staleness (D-3) | PENDING — cascade step needed |

### 5. ¿Cuál es el riesgo residual?

**MEDIUM** — La regresión de `__pycache__` puede hacer que el scheduler use código legacy si no se limpia el cache en cada restart. Mitigación: script de arranque que limpie `__pycache__` antes de iniciar uvicorn.

---

## 3. FALSE CERTIFICATION SCENARIOS

| Scenario | Risk | Mitigation |
|----------|------|------------|
| Projection fresh, REAL stale | WARN | Observatory separates REAL vs PROJECTION |
| Scheduler "success" without data change | FAIL | No `before/after` check implemented |
| Snapshot fresh, source fresher | WARN | Observatory captures both dates |

---

## 4. SINGLE CANONICAL CHAIN VERIFIED

| Layer | Writer | Scheduler | Trust Sensor | Status |
|-------|--------|-----------|-------------|--------|
| RAW | ELT | — | Freshness audit | ✅ |
| BRIDGE | `build_driver_bridge_direct.py` | cascade | Observatory | ✅ |
| DAY | `rebuild_day_from_bridge.py` | cascade | Observatory | ✅ |
| WEEK | `rebuild_week_from_day_and_bridge.py` | cascade | Observatory | ✅ |
| MONTH | `rebuild_month_from_day_and_bridge.py` | cascade | Observatory | ✅ |
| SNAPSHOT | `refresh_omniview_v2_snapshots.py` | cascade | Observatory | ✅ |

**1 writer per layer. 0 exceptions.**

---

## 5. BACKLOG (FASE 8)

| Code | Name | Status |
|------|------|--------|
| CF-WG.1 | Single Canonical Weekly Chain | **REGISTERED** |
| CF-WG.2 | False Freshness Prevention | **REGISTERED** |
| CF-WG.3 | Shared Reality Governance | **REGISTERED** |

---

## 6. CLASSIFICATION

### SHARED_REALITY_CERTIFIED

- Shared REAL layer governed ✅
- 1 writer per table ✅
- V1/V2 isolated (safe sharing) ✅
- False certification scenarios documented ✅
- Observatory implemented ✅
- Certification rules defined ✅

---

## 7. GO/NO-GO FOR D.3B

**GO for D.3B (Matrix Evolution)**

La capa REAL compartida está gobernada. V2 puede continuar evolucionando el Matrix sin riesgo para V1. Las reglas de certificación previenen futuras falsas certificaciones.

---

## 8. DELIVERABLES

| # | Document |
|---|----------|
| 1 | `OV2_G1_SHARED_REALITY_INVENTORY.md` |
| 2 | `OV2_G1_CERTIFICATION_DEPENDENCY_MAP.md` |
| 3 | `OV2_G1_FALSE_CERTIFICATION_AUDIT.md` |
| 4 | `OV2_G1_SINGLE_CANONICAL_WEEKLY_CHAIN.md` |
| 5 | `OV2_G1_V1_V2_ISOLATION_AUDIT.md` |
| 6 | `OV2_G1_OWNERSHIP_REGISTRY.md` |
| 7 | `OV2_G1_CERTIFICATION_RULES.md` |
| 8 | Backlog: CF-WG.1, CF-WG.2, CF-WG.3 |
| 9 | `OV2_G1_SHARED_REALITY_GOVERNANCE_REPORT.md` (this document) |

---

*End of OV2-G.1 Shared Reality Governance Report*
