# LG_FIX_1A_FACT_ROWCOUNT_AUDIT — Fact Rowcount Audit

**Generated:** 2026-06-12T19:36  
**DB:** `168.119.226.236:5432/yego_integral`  
**Operational date returned by backend:** `2026-06-12`  
**Date requested by UI:** `2026-06-11` (derived from operational-date)

---

## Facts Audit Table

| # | Table | Exists | Total Rows | Max Date | Rows 06-11/12 | Writer | Consumer UI | Status |
|---|-------|--------|------------|----------|---------------|--------|-------------|--------|
| 1 | `growth.yango_lima_driver_state_snapshot` | YES | 166,712 | **2026-06-12** | 37,090 | V2 Pipeline | Overview, DriverState | HEALTHY |
| 2 | `growth.yango_lima_program_eligibility_daily` | YES | 254,560 | **2026-06-12** | 56,256 | V2 Pipeline | Programs, Overview | HEALTHY |
| 3 | `growth.yego_lima_driver_lifecycle_daily` | YES | 273,908 | **2026-06-10** | **0** | V2 Pipeline | Overview | STALE |
| 4 | `growth.yego_lima_driver_taxonomy_v2_daily` | YES | 273,908 | **2026-06-10** | **0** | V2 Pipeline | Segments | STALE |
| 5 | `growth.driver_movement_fact` | YES | 68,473 | **2026-06-10** | **0** | V2 Pipeline | Movement | STALE |
| 6 | `growth.program_effectiveness_fact` | YES | **10** | 2026-06-10 | **0** | Manual/Pipeline | Effectiveness | **NEAR-EMPTY** |
| 7 | `growth.driver_program_effectiveness_fact` | YES | 68,473 | 2026-06-10 | **0** | V2 Pipeline | Effectiveness | STALE |
| 8 | `growth.yego_lima_loopcontrol_result_sync` | YES | 10 | 2026-06-08 | **0** | LoopControl sync | — | STALE |
| 9 | `growth.yego_lima_impact_tracking` | YES | **0** | NULL | **0** | — | — | EMPTY |
| 10 | `growth.yego_lima_v2_effectiveness_fact` | YES | **0** | NULL | **0** | V2 Pipeline | Effectiveness | EMPTY |
| 11 | `growth.yego_lima_v2_movement_fact` | YES | **0** | NULL | **0** | V2 Pipeline | Movement Analytics | EMPTY |
| 12 | `growth.yego_lima_driver_taxonomy_daily` | YES | 18,545 | 2026-06-10 | **0** | V1 Pipeline | Segments (legacy) | STALE |
| 13 | `growth.yego_lima_serving_fact` | YES | 56 | **2026-06-12** | 16 | Refresh | Health/Freshness | OK |
| 14 | `growth.yego_lima_v2_lifecycle_daily` | YES | 273,908 | 2026-06-10 | **0** | V2 Pipeline | Overview | STALE |
| 15 | `growth.yego_lima_v2_program_daily` | YES | 273,908 | 2026-06-10 | **0** | V2 Pipeline | Programs | STALE |
| 16 | `growth.yego_lima_v2_taxonomy_daily` | YES | 273,908 | 2026-06-10 | **0** | V2 Pipeline | Segments | STALE |

### Tablas RNA (NO existen en DB)

| Table | Exists | Impact |
|-------|--------|--------|
| `growth.rna_priority_fact` | **NO** | RNA Tab: `/rna-priority/summary` → 500 |
| `growth.rna_pilot_measurement_fact` | **NO** | RNA Tab Pilot: `/rna-pilot/summary` → 500 |

---

## Descripción de columnas relevantes por tabla

### 1. `yango_lima_driver_state_snapshot`
- **Granularity:** driver_id × snapshot_date
- **Key columns:** `driver_profile_id`, `snapshot_date`, `lifecycle_state`, `retention_state`, `performance_state`, `segment`
- **Latest data:** 2026-06-12, **37,090 rows for 2026-06-11+12**

### 2. `yango_lima_program_eligibility_daily`
- **Granularity:** driver_id × eligibility_date × program_code
- **Key columns:** `driver_profile_id`, `program_code`, `eligibility_date`, `is_eligible`, `priority_score`
- **Latest data:** 2026-06-12, **56,256 rows for 2026-06-11+12**

### 3. `yego_lima_driver_lifecycle_daily`
- **Granularity:** driver_id × snapshot_date
- **Key columns:** `driver_profile_id`, `snapshot_date`, `lifecycle_stage`, `days_since_last_trip`, `trip_count_7d`, `trip_count_30d`
- **Latest data:** 2026-06-10 — **NO DATA for 06-11 or 06-12**

### 4. `yego_lima_driver_taxonomy_v2_daily`
- **Granularity:** driver_id × snapshot_date
- **Key columns:** `driver_profile_id`, `snapshot_date`, `operational_status`, `operational_segment`, `value_overlay`, `momentum`, `persona`
- **Latest data:** 2026-06-10 — **NO DATA for 06-11 or 06-12**
- **Impact:** taxonomy/summary returns `total_drivers: 0` and empty distributions

### 5. `driver_movement_fact`
- **Granularity:** driver_id × movement_date
- **Key columns:** `driver_profile_id`, `movement_date`, `from_segment`, `to_segment`, `transition_type`, `program_code`, `movement_score`
- **Latest data:** 2026-06-10 — **NO DATA for 06-11 or 06-12**
- **Impact:** movement/summary returns all zeros

### 6. `program_effectiveness_fact`
- **Granularity:** program × evaluation_date
- **Key columns:** `program_code`, `evaluation_date`, `assigned_drivers`, `positive_moves`, `negative_moves`, `net_effect`
- **Total rows:** ONLY 10 — efectivamente **vacía**
- **Impact:** effectiveness/summary → 500

### 10. `yego_lima_v2_effectiveness_fact`
- **Total rows:** 0 — **NUNCA SE HA POBLADO**

### 11. `yego_lima_v2_movement_fact`
- **Total rows:** 0 — **NUNCA SE HA POBLADO**

---

## DIAGNÓSTICO CENTRAL: PIPELINE RUN GAP

**El pipeline V2 de Lima Growth produjo datos hasta 2026-06-10, pero NO para 2026-06-11 ni 2026-06-12.**

| Fecha | driver_state | program_eligibility | lifecycle | taxonomy_v2 | movement_fact |
|-------|-------------|---------------------|-----------|-------------|---------------|
| 2026-06-10 | YES | YES | YES (max) | YES (max) | YES (max) |
| 2026-06-11 | YES | YES | **NO** | **NO** | **NO** |
| 2026-06-12 | YES | YES | **NO** | **NO** | **NO** |

**Sin embargo, `operational-date` reporta `is_fresh: true` — FALSE POSITIVE.**

La UI pide `date=2026-06-11` (porque operational_date es 2026-06-12 y la UI resta 1 día en algunos casos o usa la fecha directamente). Los endpoints que devuelven 0 o valores vacíos para 2026-06-11 lo hacen porque la data más reciente en esas tablas es 2026-06-10.
