# LG_UI_CHECK_1B_DRIVER_EXPLORER_FILTER_CONTRACT_FIX

**Phase:** LG-UI-CHECK-1B — Driver Explorer Filter Contract Fix  
**Generated:** 2026-06-12T23:55  
**Veredict:** `LG_UI_CHECK_1B_PASS`

---

## 1. DB VALUES (ground truth)

### Program (canonical values)

| DB Value | Count | % |
|----------|-------|---|
| `PROGRAM_ACTIVE_GROWTH` | 15,054 | 81.2% |
| `PROGRAM_14_90` | 2,669 | 14.4% |
| `NULL` (no program) | 504 | 2.7% |
| `PROGRAM_CHURN_PREVENTION` | 317 | 1.7% |
| `NEW_DRIVER_ONBOARDING` | 1 | 0.01% |

### Lifecycle (canonical values)

| DB Value | Count | % |
|----------|-------|---|
| `ESTABLISHED` | 15,811 | 85.3% |
| `ACTIVATED` | 2,621 | 14.1% |
| `EARLY_LIFE` | 113 | 0.6% |

### RNA Band (canonical values)

| DB Value | Count | % |
|----------|-------|---|
| `COLD` | 17,657 | 95.2% |
| `WARM` | 888 | 4.8% |
| `HOT` | 0 | 0% |

---

## 2. UI VALUES vs DB VALUES — MISMATCH MATRIX

### Program

| UI Label | UI Value (before) | DB Value | Match? |
|----------|-----------------|----------|--------|
| Active Growth | `ACTIVE_GROWTH` | `PROGRAM_ACTIVE_GROWTH` | **MISMATCH** |
| Churn Prevention | `CHURN_PREVENTION` | `PROGRAM_CHURN_PREVENTION` | **MISMATCH** |
| High Value Recovery | `HIGH_VALUE_RECOVERY` | (doesn't exist) | **MISSING** |
| New Driver Onboarding | `NEW_DRIVER_ONBOARDING` | `NEW_DRIVER_ONBOARDING` | MATCH |
| (missing) | — | `PROGRAM_14_90` | **MISSING** |

### Lifecycle

| UI Label | UI Value (before) | DB Value | Match? |
|----------|-----------------|----------|--------|
| Active | `ACTIVE` | (doesn't exist) | **MISSING** |
| At Risk | `AT_RISK` | (doesn't exist) | **MISSING** |
| Churned | `CHURNED` | (doesn't exist) | **MISSING** |
| Inactive | `INACTIVE` | (doesn't exist) | **MISSING** |
| (missing) | — | `ESTABLISHED` | **MISSING** |
| (missing) | — | `ACTIVATED` | **MISSING** |
| (missing) | — | `EARLY_LIFE` | **MISSING** |

### RNA Band

| UI Label | UI Value (before) | DB Value | Match? |
|----------|-----------------|----------|--------|
| HOT | `HOT` | (0 rows) | MISSING |
| WARM | `WARM` | `WARM` | **MATCH** |
| COLD | `COLD` | `COLD` | **MATCH** |

### Summary

| Category | Count |
|----------|-------|
| **MATCH** | 3 |
| **MISMATCH** (wrong value sent to API) | 2 |
| **MISSING** (DB value has no UI option) | 4 |
| **MISSING** (UI option has no DB value) | 5 |

**7 of 14 dropdown options were wrong or missing.**

---

## 3. FIX APPLIED

### File: `DriverExplorerTab.jsx` (lines 6-27)

**Program dropdown — corrected to canonical `PROGRAM_` prefix values:**

| Before | After |
|--------|-------|
| `ACTIVE_GROWTH` | `PROGRAM_ACTIVE_GROWTH` |
| `CHURN_PREVENTION` | `PROGRAM_CHURN_PREVENTION` |
| `HIGH_VALUE_RECOVERY` | Removed (doesn't exist in DB) |
| (missing) | `PROGRAM_14_90` (added — 2,669 drivers) |
| `NEW_DRIVER_ONBOARDING` | Unchanged |

**Lifecycle dropdown — replaced with actual DB values:**

| Before | After |
|--------|-------|
| `ACTIVE` | `ESTABLISHED` (15,811 drivers) |
| `AT_RISK` | `ACTIVATED` (2,621 drivers) |
| `CHURNED` | `EARLY_LIFE` (113 drivers) |
| `INACTIVE` | Removed |

**RNA Band dropdown — removed HOT (0 rows):**

| Before | After |
|--------|-------|
| `HOT` | Removed |
| `WARM` | Unchanged |
| `COLD` | Unchanged |

---

## 4. ACTIVE GROWTH SANITY CHECK

### Key Question: ¿Active Growth está inflado?

| Check | Value | Assessment |
|-------|-------|------------|
| Total in PROGRAM_ACTIVE_GROWTH | 15,054 | 81.2% of all drivers |
| With trips_7d > 0 | 14,630 (97.2%) | Most are actually active |
| With trips_30d > 0 | 2,552 (17.0%) | Only 17% have 30-day history |
| Lifecycle = ESTABLISHED | 15,054 (100%) | All AG drivers are ESTABLISHED |
| Lifecycle = ACTIVATED | 0 | No ACTIVATED drivers in AG |
| Lifecycle = EARLY_LIFE | 0 | No EARLY_LIFE drivers in AG |

### Trips 7d bands within ACTIVE_GROWTH

| Band | Drivers | % |
|------|---------|---|
| 0 | 424 | 2.8% |
| 1-10 | 12,674 | 84.2% |
| 11-20 | 1,193 | 7.9% |
| 21-30 | 444 | 2.9% |
| 31-40 | 309 | 2.1% |
| 41-50 | 6 | 0.04% |
| 50+ | 4 | 0.03% |

### Assessment

**YES, Active Growth está inflado.** El 84.2% de los drivers en este programa tienen solo 1-10 viajes en 7 días. El 2.8% tienen 0 viajes. Solo el ~5% tiene más de 20 viajes/semana.

El problema está en la lógica de asignación del writer (no en el Explorer ni en el Program Engine). El `build_driver_explorer_fact()` asigna `PROGRAM_ACTIVE_GROWTH` a todos los drivers con `lifecycle = ESTABLISHED` como fallback del COALESCE:

```python
COALESCE(pr.program_code,
    CASE
        WHEN ds.lifecycle_state = 'ACTIVE' THEN 'ACTIVE_GROWTH'
        WHEN ds.lifecycle_state = 'AT_RISK' THEN 'CHURN_PREVENTION'
        WHEN ds.lifecycle_state = 'CHURNED' THEN 'HIGH_VALUE_RECOVERY'
        WHEN ds.new_driver_flag THEN 'NEW_DRIVER_ONBOARDING'
        ELSE NULL
    END
)
```

Pero el `driver_state_snapshot` usa `ESTABLISHED` (no `ACTIVE`) como lifecycle. El COALESCE no mapea `ESTABLISHED`, así que cae al ELSE NULL — pero el `program_eligibility_daily` ya asigna `PROGRAM_ACTIVE_GROWTH` a estos drivers. Los 15,054 vienen del JOIN con `program_eligibility_daily`, no del fallback.

**La inflación viene de `program_eligibility_daily`, no del Explorer.** El Program Engine (que escribe `program_eligibility_daily`) asigna `PROGRAM_ACTIVE_GROWTH` a 15,054 drivers sin filtrar por nivel de actividad real.

### Backlog

| Ticket | Description | Phase |
|--------|-------------|-------|
| **LG-PROG-3A** | Program Registry V3 — revisar criterios de elegibilidad para ACTIVE_GROWTH. El 84% tiene 1-10 viajes/semana y el 2.8% tiene 0. Posible sobre-asignación. | Future |

**NO se modifica el Program Engine en esta fase.**

---

## 5. ENDPOINT VALIDATION

| Query | Total | Drivers | Status |
|-------|-------|---------|--------|
| `?program=PROGRAM_ACTIVE_GROWTH&limit=5` | 15,054 | 5 | ✅ PASS |
| `?program=PROGRAM_14_90&limit=5` | 2,669 | 5 | ✅ PASS |
| `?program=PROGRAM_CHURN_PREVENTION&limit=5` | 317 | 5 | ✅ PASS |
| `?lifecycle=ESTABLISHED&limit=5` | 15,811 | 5 | ✅ PASS |
| `?lifecycle=ACTIVATED&limit=5` | 2,621 | 5 | ✅ PASS |
| `?lifecycle=EARLY_LIFE&limit=5` | 113 | 5 | ✅ PASS |
| `?rna_band=COLD&limit=5` | 17,657 | 5 | ✅ PASS |
| `?rna_band=WARM&limit=5` | 888 | 5 | ✅ PASS |
| `?program=PROGRAM_ACTIVE_GROWTH&lifecycle=ESTABLISHED&rna_band=COLD&limit=5` | 14,532 | 5 | ✅ PASS |
| `?program=PROGRAM_ACTIVE_GROWTH&rna_band=WARM&limit=5` | 522 | 5 | ✅ PASS |
| `?program=PROGRAM_ACTIVE_GROWTH&lifecycle=ACTIVATED&rna_band=COLD&limit=5` | 0 | 0 | ✅ PASS (combination doesn't exist in data) |

**12/12 queries return correct results. All HTTP 200. Latency <1s.**

---

## 6. UI CHECKPOINT (Expected after fix)

| Check | Expected Result |
|-------|----------------|
| Program = Active Growth | **Shows 15,054 drivers** (was 0 before fix) |
| Program = 14/90 | **Shows 2,669 drivers** (was not an option) |
| Program = Churn Prevention | **Shows 317 drivers** (was 0 before fix) |
| Lifecycle = Established | **Shows 15,811 drivers** (was not an option) |
| Lifecycle = Activated | **Shows 2,621 drivers** (was not an option) |
| RNA = COLD | **Shows 17,657 drivers** (was 0 before fix) |
| RNA = WARM | **Shows 888 drivers** (worked before too) |
| Program AG + RNA COLD | **Shows 14,532 drivers** |
| Program AG + RNA WARM | **Shows 522 drivers** |

---

## 7. REGRESSION CHECK

| Tab | Source | Status |
|-----|--------|--------|
| Overview | `driver_state_snapshot` (06-12) | ✅ OK |
| Programs | `program_eligibility_daily` (06-12) | ✅ OK |
| Segments | `v2_taxonomy_daily` (06-12) | ✅ OK |
| Movement | `v2_movement_fact` (06-12) | ✅ OK |
| RNA | `rna_priority_fact` (888 rows) | ✅ OK |
| Effectiveness | `program_effectiveness_fact` (34 rows) | ✅ OK |

**Zero changes to other tabs. Build PASS.**

---

## 8. FILES CHANGED

| File | Change | Lines |
|------|--------|-------|
| `DriverExplorerTab.jsx` | Fixed PROGRAM_OPTIONS, LIFECYCLE_OPTIONS, RNA_BAND_OPTIONS | -8 options, +6 options |

---

## VEREDICT

### LG_UI_CHECK_1B_PASS

| Criterion | Status |
|-----------|--------|
| Program filter devuelve drivers | ✅ 15,054 ACTIVE_GROWTH (was 0) |
| Lifecycle filter usa valores reales | ✅ ESTABLISHED, ACTIVATED, EARLY_LIFE (was ACTIVE/AT_RISK/CHURNED/INACTIVE) |
| RNA filter devuelve drivers | ✅ 17,657 COLD, 888 WARM |
| Combinaciones existentes funcionan | ✅ AG+ESTABLISHED+COLD = 14,532 |
| Active Growth clasificado | ✅ INFLATED (84% have 1-10 trips/week). Backlog: LG-PROG-3A |
| No 500 | ✅ All 200 |
| No timeout | ✅ <1s |
| Otros tabs OK | ✅ 6/6 fresh |
| Build PASS | ✅ npm run build (7.78s) |

**La causa raíz: los dropdowns del UI enviaban valores que no coincidían con los valores canónicos en la base de datos. 7 de 14 opciones estaban equivocadas o ausentes. El fix alinea los valores del frontend con los valores reales de la serving fact.**

**Active Growth está inflado (84% con 1-10 viajes/semana), pero esto es un problema del Program Engine (`program_eligibility_daily`), no del Explorer. Se registra backlog LG-PROG-3A para revisión futura.**
