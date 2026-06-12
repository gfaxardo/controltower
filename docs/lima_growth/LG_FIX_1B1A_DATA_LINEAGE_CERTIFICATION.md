# LG_FIX_1B1A_DATA_LINEAGE_CERTIFICATION — Data Lineage Certification

**Generated:** 2026-06-12T20:15  
**Scope:** Lineage completo UI1A → endpoint → service → query → tabla → writer → scheduler  
**Veredicto:** `DATA_LINEAGE_INCONSISTENT`

---

## 1. CADENA COMPLETA POR TAB UI1A

### 1.1 OVERVIEW

```
UI: OverviewTab.jsx
  ├─ data.overview → getLimaGrowthOperationalSummary(date)
  ├─ data.driverState → getLimaGrowthDriverStateSummary(date)
  ├─ data.operationalTruth → getLimaGrowthOperationalTruth(date)
  └─ data.movementSummary → getLimaGrowthMovementSummary({date})
```

| Endpoint | Router | Service | SQL Tables Read | Writer | Scheduler |
|----------|--------|---------|----------------|--------|-----------|
| `GET /operational-summary` | `yego_lima_operational_summary.py:20` | `yego_lima_operational_summary_service.get_operational_summary` | `yango_lima_driver_state_snapshot`, `yango_lima_program_eligibility_daily`, `yango_lima_prioritized_opportunity_daily`, `yego_lima_assignment_queue`, `yango_lima_loopcontrol_campaign_export`, `yego_lima_capacity_config`, `yango_lima_opportunity_policy_config` | `autonomous_tick` (cada 5 min) | ✅ **ACTIVO** |
| `GET /driver-state/summary` | `yego_lima_operational_summary.py:35` | `yego_lima_driver_state_summary_service.get_driver_state_summary` | `yango_lima_driver_state_snapshot` | `autonomous_tick` (cada 5 min) | ✅ **ACTIVO** |
| `GET /operational-truth` | `yego_lima_operational_truth.py:9` | `yego_lima_operational_truth_service.get_operational_truth` | 7 tables (snapshot, eligibility, prioritized, queue, LC export, policy config, intraday signal) | `autonomous_tick` (cada 5 min) | ✅ **ACTIVO** |

**Veredicto Overview:** ✅ Tablas de OP layer tienen scheduler activo. Último dato: 2026-06-12.

---

### 1.2 PROGRAMS

```
UI: ProgramsTab.jsx
  ├─ data.programs → getLimaGrowthProgramsSummary(date)
  └─ data.programStatus → getLimaGrowthProgramStatus(date)
```

| Endpoint | Router | Service | SQL Tables Read | Writer | Scheduler |
|----------|--------|---------|----------------|--------|-----------|
| `GET /programs/summary` | `yego_lima_growth_state.py:122` | `yego_lima_program_eligibility_service.get_program_summary` | `yango_lima_driver_state_snapshot`, `yango_lima_program_eligibility_daily`, `yango_lima_prioritized_opportunity_daily`, `yego_lima_assignment_queue`, `yango_lima_loopcontrol_campaign_export` | `autonomous_tick` (cada 5 min) | ✅ **ACTIVO** |
| `GET /programs/status` | `yego_lima_program_status.py:9` | `yego_lima_program_status_service.get_program_operational_status` | `yango_lima_program_eligibility_daily`, `yango_lima_prioritized_opportunity_daily`, `yego_lima_assignment_queue` | `autonomous_tick` (cada 5 min) | ✅ **ACTIVO** |

**Veredicto Programs:** ✅ Tablas de OP layer tienen scheduler activo. Último dato: 2026-06-12. Pero el payload mismatch hace que la UI muestre ceros falsos.

---

### 1.3 SEGMENTS (Taxonomy)

```
UI: SegmentsTab.jsx
  └─ data.taxonomy → getLimaGrowthTaxonomySummary(date)
```

| Endpoint | Router | Service | SQL Table Read | Writer | Scheduler |
|----------|--------|---------|---------------|--------|-----------|
| `GET /taxonomy/summary` | `yego_lima_taxonomy.py:20` | `yego_lima_taxonomy_service.get_taxonomy_summary` | **`growth.yego_lima_driver_taxonomy_daily`** | `POST /taxonomy/build` (manual) | ❌ **SIN SCHEDULER** |

**Table `yego_lima_driver_taxonomy_daily`:**
- **Tipo:** V1 Shadow Taxonomy (NO es V2)
- **Writer:** `yego_lima_taxonomy_service.build_driver_taxonomy()` → activado solo por API `POST /yego-lima-growth/taxonomy/build`
- **Scheduler:** **NINGUNO** — no hay job automático que ejecute este builder
- **Último dato:** 2026-06-10 (18,545 rows por día)

**Veredicto Segments:** ❌ **TABLA HUÉRFANA DE SCHEDULER.** La UI1A lee de `yego_lima_driver_taxonomy_daily` (V1 shadow), que SOLO se puebla mediante API manual. El V2 shadow pipeline escribe a `yego_lima_v2_taxonomy_daily` — una tabla diferente que la UI1A no consume.

---

### 1.4 MOVEMENT

```
UI: MovementTab.jsx
  ├─ data.movementSummary → getLimaGrowthMovementSummary({date})
  ├─ data.movementRecords → getLimaGrowthMovementRecords({date, limit})
  ├─ stats (direct api)  → GET /movement-analytics/stats
  ├─ matrix (direct api) → GET /movement-analytics/matrix
  ├─ winners (direct api) → GET /movement-analytics/winners
  └─ losers (direct api)  → GET /movement-analytics/losers
```

| Endpoint | Router | Service | SQL Tables Read | Writer | Scheduler |
|----------|--------|---------|----------------|--------|-----------|
| `GET /movement/summary` | `yego_lima_movement_router.py:11` | `yego_lima_movement_service.get_daily_movement_summary` | `yego_lima_program_decision_trace`, `yego_lima_state_transition_trace`, `yego_lima_driver_list_history` | `autonomous_tick` (cada 5 min) | ✅ **ACTIVO** |
| `GET /movement/records` | **RUTA NO REGISTRADA** | — | — | — | ❌ **404** |
| `GET /movement-analytics/stats` | `yego_lima_movement_analytics.py:12` | `yego_lima_movement_analytics_service.get_movement_stats` | **`growth.driver_movement_fact`** | **V2 pipeline step 7** | ❌ **04:45 cron NO CORRIÓ** |
| `GET /movement-analytics/matrix` | `yego_lima_movement_analytics.py:18` | `yego_lima_movement_analytics_service.get_transition_matrix` | **`growth.driver_movement_fact`** | **V2 pipeline step 7** | ❌ **04:45 cron NO CORRIÓ** |
| `GET /movement-analytics/winners` | `yego_lima_movement_analytics.py:24` (estimado) | `yego_lima_movement_analytics_service.get_top_winners` | **`growth.yego_lima_v2_movement_fact`** | **V2 pipeline step 7** | ❌ **TABLA VACÍA (0 rows)** |
| `GET /movement-analytics/losers` | `yego_lima_movement_analytics.py:30` (estimado) | `yego_lima_movement_analytics_service.get_top_losers` | **`growth.yego_lima_v2_movement_fact`** | **V2 pipeline step 7** | ❌ **TABLA VACÍA (0 rows)** |

**Table `driver_movement_fact`:**
- **Tipo:** Producción (NO es V2 shadow)
- **Writer:** `yego_lima_v2_daily_pipeline_service._build_movement_fact()` → escribe a `yego_lima_v2_movement_fact` (V2 shadow)
- **PERO `stats` y `matrix` leen de `driver_movement_fact` (producción)!** ¿Quién escribe `driver_movement_fact`?
- **NO HAY INSERT en el código** para `driver_movement_fact`. Debe ser poblado por script externo o migración.

**Table `yego_lima_v2_movement_fact`:**
- **Tipo:** V2 Shadow
- **Writer:** V2 pipeline step 7 → `_build_movement_fact()` → INSERT INTO `growth.yego_lima_v2_movement_fact`
- **Estado:** 0 rows — NUNCA SE HA POBLADO
- **Scheduler:** `lima_growth_v2_daily_pipeline` cron 04:45 — **NO CORRIÓ para 06-11/12**

**Veredicto Movement:** ❌ **LINEAGE INCONSISTENTE.** Stats y matrix leen de `driver_movement_fact` (producción, 68K rows hasta 06-10, sin writer conocido ni scheduler). Winners y losers leen de `v2_movement_fact` (V2 shadow, 0 rows, nunca poblado). Records es 404.

---

### 1.5 RNA

```
UI: RNATab.jsx
  ├─ data.loyaltySummary → getYangoLoyaltySummary()      ← WRONG DOMAIN!
  ├─ data.loyaltyKPIs     → getYangoLoyaltyKpis()         ← WRONG DOMAIN!
  ├─ priority (direct api) → GET /rna-priority/summary     ← 500
  ├─ topHot (direct api)   → GET /rna-priority/drivers     ← 500
  └─ pilot (direct api)    → GET /rna-pilot/summary        ← 500
```

| Endpoint | Router | Service | SQL Tables Read | Writer | Scheduler |
|----------|--------|---------|----------------|--------|-----------|
| `GET /yango-loyalty/summary` | `yango_loyalty.py:73` | `yango_loyalty_service.get_loyalty_summary` | `ops.mv_driver_lifecycle_monthly_kpis`, `ops.v_dim_park_resolved`, `ops.yango_loyalty_kpi_manual`, `ops.yango_loyalty_targets` | Manual | ❌ **Yango Loyalty KPIs (otro dominio)** |
| `GET /rna-priority/summary` | `yego_lima_rna_priority.py:17` | `yego_lima_rna_priority_service.get_rna_priority_summary` | **`growth.rna_priority_fact`** | `POST /rna-priority/build` (manual) | ❌ **SIN SCHEDULER** |
| `GET /rna-pilot/summary` | `yego_lima_rna_pilot.py:17` (estimado) | `yego_lima_rna_pilot_measurement_service.get_pilot_summary` | **`growth.rna_pilot_measurement_fact`** | — | ❌ **TABLA NO EXISTE** |

**Table `rna_priority_fact`:**
- **Tipo:** Producción
- **Writer:** `yego_lima_rna_priority_service.build_rna_priority()` → activado solo por API `POST /yego-lima-growth/rna-priority/build`
- **Scheduler:** **NINGUNO**
- **Último dato:** ¿0 rows? — tabla existe (migración 217) pero posiblemente vacía.

**Table `rna_pilot_measurement_fact`:**
- **Tipo:** Producción
- **Writer:** Desconocido — tabla creada por migración 218 pero no hay writer en el código
- **Scheduler:** **NINGUNO**

**Veredicto RNA:** ❌ **LINEAGE ROTO.**
- La UI consume `yango-loyalty/summary` (KPIs mensuales de otro dominio) esperando campos RNA que no existen
- El endpoint real `/rna-priority/summary` lee `rna_priority_fact` que no tiene scheduler ni datos
- `rna_pilot_measurement_fact` existe pero está vacía y sin writer

---

### 1.6 EFFECTIVENESS

```
UI: EffectivenessTab.jsx (useEffect propio, no hook)
  └─ getEffectivenessSummary()
```

| Endpoint | Router | Service | SQL Tables Read | Writer | Scheduler |
|----------|--------|---------|----------------|--------|-----------|
| `GET /effectiveness/summary` | `yego_lima_effectiveness.py:12` | `yego_lima_effectiveness_service.get_effectiveness_summary` | **`growth.program_effectiveness_fact`**, **`growth.driver_program_effectiveness_fact`** | **V2 pipeline step 9** | ❌ **04:45 cron NO CORRIÓ** |

**Table `program_effectiveness_fact`:**
- **Tipo:** Producción
- **Writer:** `yego_lima_v2_daily_pipeline_service._build_effectiveness_facts()` (step 9)
- **Scheduler:** `lima_growth_v2_daily_pipeline` cron 04:45
- **Último dato:** 10 rows total, max 2026-06-10

**Table `driver_program_effectiveness_fact`:**
- **Tipo:** Producción
- **Writer:** `yego_lima_v2_daily_pipeline_service._build_effectiveness_facts()` (step 9)
- **Scheduler:** `lima_growth_v2_daily_pipeline` cron 04:45
- **Último dato:** 68,473 rows, max 2026-06-10

**Veredicto Effectiveness:** ❌ **SCHEDULER NO CORRIÓ.** Las tablas tienen scheduler (V2 pipeline 04:45), pero el scheduler no generó datos para 06-11 ni 06-12. Además, `program_effectiveness_fact` tiene solo 10 rows (insuficiente). El endpoint lanza 500 por falta de datos.

---

## 2. ¿UI1A CONSUME PROD O V2?

| Dominio | Tabla leída por UI1A | Tipo de tabla | ¿V2? |
|---------|---------------------|---------------|------|
| **Taxonomy** | `yego_lima_driver_taxonomy_daily` | V1 Shadow (manual) | **NO** |
| **Movement (stats/matrix)** | `driver_movement_fact` | Producción (sin writer) | **NO** |
| **Movement (winners/losers)** | `yego_lima_v2_movement_fact` | V2 Shadow (vacía) | **SÍ** |
| **Effectiveness** | `program_effectiveness_fact` + `driver_program_effectiveness_fact` | Producción (V2 pipeline step 9) | **NO** (son production tables, no llevan "v2_") |
| **RNA** | `rna_priority_fact` + `yango-loyalty/*` | Producción (sin scheduler) + Yango Loyalty (otro dominio) | **NO** |

**Respuesta:** UI1A consume **PRODUCCIÓN** para effectiveness y movement-analytics. **V1 SHADOW** para taxonomy. **YANGO LOYALTY (otro dominio)** para RNA. Solo winners/losers (movement-analytics) consumen **V2 SHADOW**.

**El V2 shadow pipeline (04:45) escribe tablas V2 que en su mayoría NO son consumidas por UI1A.** Las tablas V2 shadow son un espejo no utilizado por el frontend actual.

---

## 3. TABLAS HUÉRFANAS (sin scheduler)

| Tabla | Dónde se lee | Writer | Por qué huérfana |
|-------|-------------|--------|-----------------|
| `yego_lima_driver_lifecycle_daily` | V2 pipeline step 4 (read source), RNA build (read source) | `POST /lifecycle/build` (manual) | **No hay scheduler que ejecute el builder** |
| `yego_lima_driver_taxonomy_daily` | UI1A Segments tab | `POST /taxonomy/build` (manual) | **UI1A consume tabla que no tiene escritor automático** |
| `rna_priority_fact` | UI1A RNA tab (cuando no esté roto) | `POST /rna-priority/build` (manual) | **Tabla sin scheduler ni datos** |
| `rna_pilot_measurement_fact` | UI1A RNA Pilot sub-sección | **NO TIENE WRITER** | **Tabla existe (migración 218) pero nadie la puebla** |

---

## 4. TABLAS SHADOW (V1 vs V2)

| Tabla V1 Shadow | Tabla V2 Shadow | ¿UI1A consume? |
|----------------|-----------------|----------------|
| `yego_lima_driver_taxonomy_daily` (18K/día) | `yego_lima_v2_taxonomy_daily` (68K/día) | ✅ V1 shadow |
| — | `yego_lima_v2_lifecycle_daily` (68K/día) | ❌ No |
| — | `yego_lima_v2_program_daily` (68K/día) | ❌ No |
| — | `yego_lima_v2_movement_fact` (0 rows) | ✅ Solo winners/losers |
| — | `yego_lima_v2_activity_daily/weekly/monthly` | ❌ No |
| — | `yego_lima_v2_effectiveness_fact` (0 rows) | ❌ No |
| — | `yego_lima_v2_observability_fact` | ❌ No |
| — | `yego_lima_v2_freshness_registry` | Parcial (health/operability) |

**El V2 shadow pipeline produce 9 tablas shadow, de las cuales la UI1A solo consume 2 indirectamente (`v2_movement_fact` para winners/losers, `v2_freshness_registry` para health). Las 7 restantes son datos huérfanos sin consumidor frontend.**

---

## 5. TABLAS LEGACY / MUERTAS

| Tabla | Estado | Por qué |
|-------|--------|---------|
| `yego_lima_driver_taxonomy_v2_daily` | **SIN WRITER** | Tabla existe con 273,908 rows (06-10) pero NO hay INSERT en ningún servicio del código. Poblada externamente. |
| `driver_movement_fact` | **SIN WRITER** | Tabla existe con 68,473 rows (06-10) pero NO hay INSERT en ningún servicio del código. Poblada externamente. |
| `yego_lima_v2_effectiveness_fact` | **VACÍA (0 rows)** | V2 pipeline step 9 la escribe pero nunca se ha ejecutado con datos suficientes. |
| `yego_lima_v2_movement_fact` | **VACÍA (0 rows)** | V2 pipeline step 7 la escribe pero `SKIPPED_NO_NEW_DATA` porque sus fuentes no tienen datos frescos. |

---

## 6. RESUMEN DE LINEAGE POR CAPA

```
CAPA UI1A
  ├─ Overview        ──► OP tables (scheduler ✅, data ✅)
  ├─ Programs        ──► OP tables (scheduler ✅, data ✅, payload mismatch ❌)
  ├─ Segments        ──► V1 shadow taxonomy (NO scheduler ❌, data stale ❌)
  ├─ Movement        ──► driver_movement_fact (NO writer ❌) + v2_movement_fact (vacía ❌)
  ├─ RNA             ──► Yango Loyalty (wrong domain ❌) + rna_priority_fact (sin scheduler ❌)
  └─ Effectiveness   ──► effectiveness facts (V2 pipeline no corrió ❌, 10 rows)

CAPA BACKEND
  ├─ autonomous_tick (5 min)  ──► snapshot, eligibility, opportunities, queue, signals ✅
  ├─ run_daily_refresh        ──► assignment queue, serving facts ✅
  ├─ V2 pipeline (04:45 cron) ──► V2 shadow tables (7 sin consumidor, 0 rows en 2) ❌
  └─ MANUAL ONLY              ──► lifecycle_daily, taxonomy_daily, rna_priority_fact ❌

CAPA DB
  ├─ 7 OP tables con scheduler activo ✅
  ├─ 3 tablas huérfanas de scheduler ❌
  ├─ 9 V2 shadow tables (7 sin consumidor UI1A) ⚠️
  ├─ 1 V1 shadow tabla (consumida por UI1A) ⚠️
  └─ 2 tablas sin writer conocido ❌
```

---

## 7. VEREDICTO FINAL

```
DATA_LINEAGE_INCONSISTENT
```

**4 problemas estructurales de lineage detectados:**

1. **Tablas sin scheduler:** `lifecycle_daily`, `taxonomy_daily` (V1), `rna_priority_fact` requieren API calls manuales para poblarse. No hay automatización.

2. **Tablas sin writer:** `driver_movement_fact` y `yego_lima_driver_taxonomy_v2_daily` son leídas por UI1A pero no tienen INSERT en el código Python del backend. Deben ser pobladas por scripts externos o migraciones no rastreadas.

3. **V2 Shadow Pipeline produce datos huérfanos:** 7 de 9 tablas V2 shadow no son consumidas por UI1A. La pipeline de 04:45 gasta recursos produciendo datos que nadie lee.

4. **UI1A lee de V1 shadow para taxonomy, no de V2:** `yego_lima_driver_taxonomy_daily` (V1, 18K rows/día) es la fuente del Segments tab, mientras que `yego_lima_v2_taxonomy_daily` (V2, 68K rows/día) existe pero UI1A no la toca.

**Recomendación para LG-FIX-1B.2:**
- Migrar Segments tab a leer de `yego_lima_v2_taxonomy_daily` (V2 shadow) o de `yego_lima_driver_taxonomy_v2_daily` (producción)
- Agregar builders de lifecycle, taxonomy y movement al `autonomous_tick` o al `run_daily_refresh`
- Implementar writer para `rna_priority_fact` en el scheduler
- Eliminar o conectar las 7 tablas V2 shadow huérfanas a consumidores reales
- Arreglar el payload mismatch en Programs y Overview tabs
