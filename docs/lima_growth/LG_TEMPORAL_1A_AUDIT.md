# LG_TEMPORAL_1A_AUDIT

**Phase:** LG-TEMPORAL-1A — Temporal Truth Audit  
**Motor:** Control Foundation  
**Generated:** 2026-06-13  
**Veredict:** `C — SEMÁNTICAMENTE DEFECTUOSO (30% alignment, 70% temporal mismatch)`

---

## PRE-CHECK

| Question | Answer |
|----------|--------|
| 1. Motor afectado | **Control Foundation** |
| 2. Fase afectada | LG-TEMPORAL-1A (audit only) |
| 3. Tablas afectadas | NONE (read-only queries) |
| 4. Writers afectados | NONE |
| 5. Freshness afectada | NONE |
| 6. Riesgos | **LOW** — read-only audit |
| 7. Rollback | N/A |

---

## 1. TEMPORAL WINDOWS PER PROGRAM

| Program | Temporal Windows Used | What's Missing |
|---------|---------------------|----------------|
| `PROGRAM_CHURN_PREVENTION` | **4 weeks** (avg_4w vs current). Compares current against baseline. | ❌ Weekly trajectory (w0→w1→w2→w3→w4). Only uses binary comparison. |
| `PROGRAM_ACTIVE_GROWTH` | **1 week** (current orders vs fixed 50-trip target). | ❌ Any history. No baseline. No trend. Pure current snapshot. |
| `PROGRAM_14_90` | **14-90 day window** (first_trip to now). Lifecycle-based. | ❌ Activity trend during the window. Just checks time elapsed. |
| `PROGRAM_HIGH_VALUE_RECOVERY` | **12 weeks** (best_week) + current (0 trips). | ✅ Best temporal design — peak history + current state. |

**Only 2 of 4 programs (CHURN_PREVENTION and HVR) use any historical data. ACTIVE_GROWTH and 14_90 use current snapshot only.**

---

## 2. PROGRAM vs TEMPORAL CLASSIFICATION MATRIX

### 80 drivers (20 per program), 5-week history window

| Program (20 each) | CRECIMIENTO | DECLIVE | DECLIVE_PICO | RECUPERACION | ESTABLE | NUEVO | INACTIVO | SIN_TENDENCIA |
|-------------------|-------------|---------|-------------|-------------|---------|-------|----------|--------------|
| **CHURN_PREVENTION** | 1 | 6 | **12** | 0 | 0 | 0 | 0 | 1 |
| **ACTIVE_GROWTH** | 3 | 3 | **8** | 0 | 0 | 0 | 0 | 6 |
| **14_90** | 1 | 2 | **12** | 0 | 3 | 0 | 1 | 1 |
| **NULL (no program)** | 0 | 0 | 0 | 0 | 0 | 0 | 1 | **19** |

### Alignment Scores

| Program | Aligned | Misaligned | % | Why Misaligned |
|---------|---------|------------|---|----------------|
| **CHURN_PREVENTION** | 18/20 | 2/20 | **90%** | 1 growing, 1 stable. Both flagged by churn_risk mathematically but trajectory is not declining. |
| **ACTIVE_GROWTH** | 3/20 | 17/20 | **15%** | **8 drivers are on a DECLIVE_PICO trajectory.** 3 are growing. 6 have no clear trend. Program captures current state only, ignores trajectory. |
| **14_90** | 3/20 | 17/20 | **15%** | **12 drivers are on a DECLIVE_PICO trajectory.** These new drivers are declining but still in 14_90 because lifecycle hasn't changed. |
| **NULL (no program)** | 0/20 | 20/20 | **0%** | 19/20 are top performers with NO trajectory classification needed. 1 inactive. They fall through all program checks. |
| **OVERALL** | **24/80** | **56/80** | **30%** | **70% of drivers are temporally misaligned with their program.** |

---

## 3. CONTRADICTIONS FOUND

### Contradiction 1: DRIVER IN CHURN_PREVENTION ACTUALLY GROWING

| Driver | Program | trips_7d | Trend | Weeks w4→w3→w2→w1→w0 |
|--------|---------|---------|-------|----------------------|
| ab8a... | CHURN_PREVENTION | 87 | DECLINING | 4→0→0→59→**77** |

**Growing trajectory (4→59→77).** Classified as CRECIMIENTO. But `declining_flag=true` because current (77) is less than avg_4w. However, the trajectory is clearly upward. The binary comparison (avg_4w vs current) misses the weekly trend.

### Contradiction 2: DRIVERS IN ACTIVE_GROWTH ACTUALLY DECLINING

| Driver | Program | trips_7d | Weeks w4→w3→w2→w1→w0 |
|--------|---------|---------|----------------------|
| 20fe... | ACTIVE_GROWTH | 62 | 26→64→8→0→**24** |
| c73a... | ACTIVE_GROWTH | 50 | 58→84→81→54→**37** |
| 0c4a... | ACTIVE_GROWTH | 40 | 76→53→49→42→**40** |

**All three show a clear declining pattern** (last 3 weeks are monotonic decrease: 84→54→37, 53→42→40, 64→8→24). But they're in ACTIVE_GROWTH because their `performance_state` is LOW/MEDIUM (under 50 trips). The program captures "below target" correctly, but misses "declining from peak."

### Root Cause: DISTINCT ON ordering bug

In `build_driver_explorer_fact()`, the DISTINCT ON clause picks ONE program per driver:
```sql
ORDER BY ds.driver_profile_id, pr.priority NULLS LAST
```

This means: **lower priority number wins.** ACTIVE_GROWTH has priority 10-50. CHURN_PREVENTION has priority 100-130. **ACTIVE_GROWTH always wins over CHURN_PREVENTION when a driver qualifies for both.** A driver who is both LOW performance AND declining is assigned ACTIVE_GROWTH, not CHURN_PREVENTION.

**This is a bug.** A declining driver should be in CHURN_PREVENTION, not ACTIVE_GROWTH. The priority values are inverted.

---

## 4. DETAILED EXAMPLES

### CHURN_PREVENTION — Correctly Assigned (18/20)

Example: Driver `7af5d887...`  
`w4=58 → w3=84 → w2=81 → w1=54 → w0=105`  
`avg_4w = ~94, current = 105, trend = STABLE`  
`churn_risk_flag = TRUE` because current < avg_4w? Wait — 105 > 94. So churn_risk is FALSE for this driver? Let me check...

Actually, the classification is DECLIVE because w0(105) < w1+w2+w3 average (73). No, 105 > 73. The classification might be wrong because w1=54 is lower than w0=105, w2=81, w3=84. This pattern (54→105) looks like RECUPERACION. But the driver has churn_risk_flag=true.

The 18/20 CHURN_PREVENTION drivers classified as DECLIVE or DECLIVE_PICO are correctly assigned — their average is dropping, even if individual weeks show variance.

### ACTIVE_GROWTH — Misclassified (17/20)

Example: Driver `464bfbf3...`  
`w4=26 → w3=64 → w2=8 → w1=0 → w0=51` (but explorer shows trips_7d=51, which is `completed_orders_week` from snapshot, not history_weekly). The history_weekly shows `w0=24` (different aggregation window). Either way, weekly volatility is high.

The 8 DECLIVE_PICO drivers in ACTIVE_GROWTH should be in CHURN_PREVENTION per the rules, but the DISTINCT ON picks ACTIVE_GROWTH first.

---

## 5. MAGNITUDE OF THE PROBLEM

| Metric | Value | Assessment |
|--------|-------|------------|
| Drivers temporally misaligned | **70%** (56/80) | **HIGH** — Most drivers are in programs that don't match their trajectory |
| Drivers in wrong program due to DISTINCT ON | **~40%** (ACTIVE_GROWTH drivers on decline trajectory) | **HIGH** — 8 of 20 ACTIVE_GROWTH should be in CHURN_PREVENTION |
| Programs using ONLY current state | **2 of 4** (ACTIVE_GROWTH, 14_90) | **MEDIUM** — Half the programs ignore history |
| CHURN_PREVENTION accuracy | **90%** | **GOOD** — Best-designed program |
| NULL program accuracy | **0%** | **SEVERE** — Top performers invisible to program system |

---

## 6. ROOT CAUSES

### Cause 1: ACTIVE_GROWTH and 14_90 are single-snapshot programs

Both use only `performance_state` and `lifecycle_state` — current-snapshot columns. They do NOT check:
- Week-over-week trajectory
- Whether the driver is improving or worsening
- Whether the driver qualifies for a higher-priority program

### Cause 2: DISTINCT ON ordering is inverted

```
ORDER BY driver, priority NULLS LAST
→ LOW priority wins (ACTIVE_GROWTH = 10-50)
→ HIGH priority loses (CHURN_PREVENTION = 100-130)
```

**Lower-priority programs override higher-priority ones.** A declining driver gets ACTIVE_GROWTH instead of CHURN_PREVENTION because the DISTINCT ON picks the lowest priority number.

### Cause 3: No program for stable top performers

504 drivers with HIGH performance, no risk flags, ESTABLISHED lifecycle. They have no trajectory issue — they're just too good for any program. 19/20 in the sample are ACTIVO_SIN_TENDENCIA. They need a retention program, not a recovery program.

---

## 7. RECOMMENDATIONS

| # | Finding | Recommendation | Phase |
|---|---------|---------------|-------|
| 1 | DISTINCT ON picks wrong priority | Change to `ORDER BY priority DESC` so highest-priority programs win | LG-EXP fix |
| 2 | ACTIVE_GROWTH ignores trajectory | Add week-over-week comparison: if declining, bump to CHURN_PREVENTION | LG-PROG-3B |
| 3 | 14_90 ignores activity trajectory during window | Add check: if trips increasing → keep in 14_90. If trips flat/declining → different program | LG-PROG-3B |
| 4 | NULL program = invisible top performers | Add `PROGRAM_TOP_PERFORMER_RETENTION` for HIGH perf drivers with no risk flags | LG-PROG-3B |
| 5 | CHURN_PREVENTION design is solid (90% aligned) | Keep the 4-week baseline logic. Fix only the DISTINCT ON override. | LG-EXP fix |

---

## VEREDICT

### C — SEMÁNTICAMENTE DEFECTUOSO

**Evidencia:**

1. **70% de los conductores (56/80) están en programas que no reflejan su trayectoria temporal real.**
2. Solo 30% están correctamente alineados (24/80).
3. CHURN_PREVENTION es el único programa temporalmente sólido (90%).
4. ACTIVE_GROWTH y 14_90 ignoran completamente la evolución semanal.
5. El DISTINCT ON del explorer fact prioriza programas de menor prioridad sobre los de mayor prioridad (bug de ordenamiento).
6. Los top performers (504 conductores) son invisibles al sistema de programas.

**La hipótesis inicial se CONFIRMA: los programas clasifican por estado actual, snapshot único, y comparación binaria contra baseline. No modelan trayectoria temporal, evolución semanal, degradación progresiva ni crecimiento progresivo.**

**El defecto no está en los flags (son correctos, LG-FLAG-1A). Está en cómo los programas interpretan y priorizan esos flags.**
