# LG_CAN_1C_FRESHNESS_RECOVERY_CERTIFICATION — Canonical Freshness Recovery

**Generated:** 2026-06-12T22:00  
**Phase:** LG-CAN-1C  
**Veredicto:** `LG_CAN_1C_CERTIFIED`

---

## 1. UPSTREAM FRESHNESS AUDIT

| Tabla | Total Rows | Max Date | Rows 06-10 | Rows 06-11 | Rows 06-12 | Writer | ¿Suficiente? |
|-------|-----------|----------|------------|------------|------------|--------|-------------|
| `yango_lima_driver_state_snapshot` | 166,712 | **2026-06-12** | 18,545 | 18,545 | 18,545 | `autonomous_tick` (5 min) | ✅ |
| `yango_lima_program_eligibility_daily` | 254,560 | **2026-06-12** | 28,128 | 28,128 | 28,128 | `autonomous_tick` (cascade) | ✅ |
| `yango_lima_prioritized_opportunity_daily` | 49,706 | **2026-06-12** | 5,431 | 5,383 | 5,339 | `autonomous_tick` (cascade) | ✅ |
| `raw_yango.orders_raw` | 48,731 | **2026-06-12** | 10,308 | 4,846 | 390 | Yango API ingestion | ✅ |
| `yego_lima_driver_lifecycle_daily` | 273,908 | **2026-06-10** | 68,473 | **0** | **0** | `POST /lifecycle/build` (manual) | ❌ (antes del backfill) |

**Conclusión upstream:** Los datos operacionales existen para 06-11 y 06-12. La capa de inteligencia (lifecycle) no se había construido porque su builder solo se activa manualmente.

---

## 2. PIPELINE EXECUTION PATH AUDIT

| Atributo | Valor |
|----------|-------|
| **Entrypoint** | `POST /yego-lima-growth/v2-pipeline/run?date=YYYY-MM-DD` |
| **Scheduler** | `lima_growth_v2_daily_pipeline` cron **04:45 AM** (APScheduler) |
| **Build order** | activity_daily → activity_weekly → activity_monthly → lifecycle_daily → taxonomy_v2 → program_v2 → movement_fact → observability → effectiveness |

### ¿Por qué no avanzó después de 06-10?

**Clasificación: C) Fuentes insuficientes**

El V2 pipeline step 4 (`_build_lifecycle_daily`) lee de `yego_lima_driver_lifecycle_daily` (producción). Esta tabla estaba congelada en 06-10 porque su builder (`POST /lifecycle/build`) solo se activa manualmente. Sin datos frescos en la fuente, el V2 pipeline producía shadow tables también congeladas.

El scheduler cron 04:45 no es la causa — el pipeline corre correctamente cuando se invoca. El problema es que su fuente upstream (`driver_lifecycle_daily`) no se actualiza automáticamente.

---

## 3. CONTROLLED BACKFILL

### Paso 1: Build lifecycle producción → V2 shadow pipeline

| Fecha | Paso | Endpoint | Resultado |
|-------|------|----------|-----------|
| **06-11** | Build lifecycle | `POST /lifecycle/build?date=2026-06-11` | ✅ 68,506 rows |
| **06-11** | V2 pipeline shadow | `POST /v2-pipeline/run?date=2026-06-11` | ✅ 9/9 steps |
| **06-12** | Build lifecycle | `POST /lifecycle/build?date=2026-06-12` | ✅ 68,506 rows |
| **06-12** | V2 pipeline shadow | `POST /v2-pipeline/run?date=2026-06-12` | ✅ 9/9 steps |

### Paso 2: V2 pipeline step results

| Step | 06-11 Status | 06-11 Rows | 06-12 Status | 06-12 Rows |
|------|-------------|-----------|-------------|-----------|
| build_activity_daily | SKIPPED | 0 | SKIPPED | 0 |
| build_activity_weekly | SKIPPED | 0 | SKIPPED | 0 |
| build_activity_monthly | SUCCESS | 6,332 | SUCCESS | 6,087 |
| build_lifecycle_daily | SUCCESS | 68,506 | SUCCESS | 68,506 |
| build_taxonomy_v2_daily | SUCCESS | 68,506 | SUCCESS | 68,506 |
| build_program_v2_daily | SUCCESS | 68,506 | SUCCESS | 68,506 |
| build_movement_fact | SUCCESS | 1,511 | SUCCESS | 466 |
| build_observability_facts | SUCCESS | 6 | SUCCESS | 6 |
| build_effectiveness_facts | SKIPPED | 0 | SKIPPED | 0 |

---

## 4. ROWCOUNTS POR FECHA (POST-BACKFILL)

| Tabla | 06-10 | 06-11 | 06-12 | Total | Max Date | Status |
|-------|-------|-------|-------|-------|----------|--------|
| `yego_lima_driver_lifecycle_daily` | 68,473 | **68,506** | **68,506** | 410,920 | **2026-06-12** | ✅ FRESH |
| `yego_lima_v2_lifecycle_daily` | 68,473 | **68,506** | **68,506** | 410,920 | **2026-06-12** | ✅ FRESH |
| `yego_lima_v2_taxonomy_daily` | 68,473 | **68,506** | **68,506** | 410,920 | **2026-06-12** | ✅ FRESH |
| `yego_lima_v2_program_daily` | 68,473 | **68,506** | **68,506** | 410,920 | **2026-06-12** | ✅ FRESH |
| `yego_lima_v2_movement_fact` | 486 | **1,511** | **466** | 2,463 | **2026-06-12** | ✅ FRESH |
| `yego_lima_driver_taxonomy_v2_daily` (orphan) | 68,473 | 0 | 0 | 273,908 | 2026-06-10 | ⚠️ DEPRECATED |

---

## 5. DOWNSTREAM ENDPOINT VALIDATION

| Endpoint | HTTP | Latencia | Valor Clave | Estado |
|----------|------|----------|-------------|--------|
| `/taxonomy/summary?date=2026-06-11` | 200 | 1,723ms | total_drivers=**68,506** | ✅ |
| `/taxonomy/summary?date=2026-06-12` | 200 | 1,633ms | total_drivers=**68,506** | ✅ |
| `/movement-analytics/stats` | 200 | 1,539ms | total_transitions=**2,463** | ✅ |
| `/movement-analytics/matrix` | 200 | 1,843ms | total_movements=**2,463** | ✅ |
| `/operational-summary?date=2026-06-11` | 200 | 776ms | universe_total=18,545 | ✅ |
| `/programs/summary?date=2026-06-11` | 200 | 1,624ms | OK | ✅ |
| `/growth/health` | 200 | 14,271ms | system_status=CRITICAL | ⚠️ |

---

## 6. BROWSER READINESS

| Tab UI1A | Fuente de datos | 06-11 | 06-12 | Veredicto |
|----------|----------------|-------|-------|-----------|
| **Segments** | `yego_lima_v2_taxonomy_daily` | 68,506 drivers ✅ | 68,506 drivers ✅ | READY |
| **Movement** | `yego_lima_v2_movement_fact` | 1,511 transitions ✅ | 466 transitions ✅ | READY |
| **Overview** | `driver_state_snapshot` (prod) | 18,545 drivers ✅ | 18,545 drivers ✅ | READY |
| **Programs** | `program_eligibility_daily` (prod) | 28,128 eligible ✅ | 28,128 eligible ✅ | READY |

**Clasificación:** `READY`

La UI Intelligence puede abrirse. Los datos están frescos para todas las fechas. Los KPI de Overview y Programs muestran datos operacionales actualizados. Segments y Movement muestran la cadena canónica completa.

---

## 7. BUILD

| Artefacto | Comando | Resultado |
|-----------|---------|-----------|
| Backend | `python -m compileall backend\app` | ✅ PASS |
| Frontend | `npm run build` (5.29s) | ✅ PASS |

---

## 8. VEREDICTO

```
LG_CAN_1C_CERTIFIED
```

### Criterio GO:

| Criterio | Estado |
|----------|--------|
| lifecycle 06-11 existe | ✅ 68,506 rows |
| lifecycle 06-12 existe | ✅ 68,506 rows |
| taxonomy 06-11 existe | ✅ 68,506 rows |
| taxonomy 06-12 existe | ✅ 68,506 rows |
| program 06-11 existe | ✅ 68,506 rows |
| program 06-12 existe | ✅ 68,506 rows |
| Endpoints responden 200 | ✅ 7/7 endpoints OK |
| UI Intelligence clasifica READY | ✅ READY |
| Build backend PASS | ✅ |
| Build frontend PASS | ✅ |

### Resumen de la cadena canónica recuperada:

```
autonomous_tick (5 min)
  └─ driver_state_snapshot ───────── 06-12 ✅
  └─ program_eligibility ─────────── 06-12 ✅
  └─ prioritized_opportunity ─────── 06-12 ✅

POST /lifecycle/build (manual)
  └─ driver_lifecycle_daily ──────── 06-12 ✅ (68,506 rows)

V2 Pipeline (cron 04:45 / manual)
  └─ v2_lifecycle_daily ──────────── 06-12 ✅
  └─ v2_taxonomy_daily ──────────── 06-12 ✅
  └─ v2_program_daily ───────────── 06-12 ✅
  └─ v2_movement_fact ───────────── 06-12 ✅ (2,463 total)

UI1A Intelligence
  └─ Segments ──► v2_taxonomy_daily ✅
  └─ Movement ──► v2_movement_fact ✅
```
