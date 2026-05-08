# Cierre incidente freshness — Fase 1.3 (post-fix validation)

**Fecha:** 2026-05-08 (America/Lima, `CURRENT_DATE` alineado con host)  
**Alcance:** validación tras migraciones **135** (MV hourly-first → `v_real_trip_fact_v2`) y **136** (restauración vistas rollup/cobertura).

---

## 1. Pipeline ejecutado (controlado)

Comando (salta hourly-first y populate drill, ya validados como frescos):

```bash
cd backend && python -m scripts.run_pipeline_refresh_and_audit --skip-hourly-first --skip-drill-populate
```

| Paso | Resultado |
|------|-----------|
| `ops.refresh_driver_lifecycle_mvs()` | OK (~5 min) |
| `refresh_supply_alerting_mvs()` | OK |
| `run_data_freshness_audit` | OK (escritura `ops.data_freshness_audit`) |
| `audit_trips_2026_commercial_coverage` | **FAIL (exit 1)** — comisión % y `pago_corporativo` por semanas abr 2026 bajo umbral (véase §5) |
| `audit_real_margin_source_gaps` | Completado (warnings/códigos según script) |

**Exit code 1** del script completo se debe **solo** a la auditoría de cobertura comercial `trips_2026`, no a fallo de refresh de MVs.

---

## 2. Evidencia BD (snapshots)

Script: `python -m scripts.validate_closure_post_fix` (solo lectura).

### 2.1 Vistas dependientes — sin `relation does not exist`

| Objeto | Filas (COUNT\*) |
|--------|------------------|
| `ops.real_rollup_day_fact` | 5 991 |
| `ops.mv_real_rollup_day` | 5 991 |
| `ops.v_real_lob_coverage` | 1 |
| `ops.v_real_data_coverage` | 2 |
| `ops.v_revenue_quality_daily_summary` | 960 |

### 2.2 MV horaria — fuente viva

`pg_matviews.definition` de `ops.mv_real_lob_hour_v2` comienza por:

`SELECT v_real_trip_fact_v2.trip_date, ...`  

(confirma lectura desde **fact vivo**, no `staging_bootstrap_*`).

### 2.3 Fechas máximas (alineación cadena)

| Métrica | Valor |
|---------|--------|
| `v_real_trip_fact_v2` MAX | 2026-05-07 |
| `mv_real_lob_day_v2` MAX(`trip_date`) | 2026-05-07 |
| `real_rollup_day_fact` MAX(`trip_day`) | 2026-05-07 |
| `mv_real_lob_week_v3` MAX(`week_start`) | 2026-05-04 |
| `mv_real_lob_month_v3` MAX(`month_start`) | 2026-05-01 |
| `mv_driver_lifecycle_base` MAX(`last_completed_ts`) | 2026-05-08 |
| `mv_driver_weekly_stats` MAX(`week_start`) | 2026-05-04 |
| `mv_supply_segments_weekly` MAX(`week_start`) | 2026-05-04 |

La semana ISO máxima en agregados **2026-05-04** es coherente con el calendario (semana en curso / cierre semanal); el día operacional REAL sigue en **2026-05-07**.

---

## 3. `ops.data_freshness_audit` (última corrida por dataset)

| Dataset | source_max | derived_max | Status |
|---------|------------|-------------|--------|
| real_operational | 2026-05-07 | 2026-05-07 | **OK** |
| real_lob | 2026-05-07 | 2026-05-07 | **OK** |
| real_lob_drill | 2026-05-07 | 2026-05-07 | **OK** |
| driver_lifecycle | 2026-05-08 | 2026-05-08 | **OK** |
| supply_weekly | 2026-05-04 | 2026-05-04 | **OK** |
| trips_2026 | 2026-05-07 | — | **OK** |
| trips_base (legacy `trips_all`) | 2026-01-31 | — | **SOURCE_STALE** (esperado; no bloquea banner REAL operacional) |
| driver_lifecycle_weekly | 2026-05-08 | 2026-05-04 | **DERIVED_STALE** |

**Nota `driver_lifecycle_weekly`:** el derivado mide **semana** (`week_start`); la fuente del audit usa timestamp diario en base hasta 2026-05-08. El “retraso” frente a la última semana cerrada en expectativa es **semántica grain week vs day**, no rotura de pipeline tras refresh. Tratamiento: **no bloqueante** para cierre del incidente de **hourly-first / Omniview / Plan vs Real**, salvo que negocio exija redefinir expectativa o columna audit para weekly.

---

## 4. Smoke tests HTTP (backend local `http://127.0.0.1:8000`)

| Endpoint | HTTP | Tiempo (ms) | Notas |
|----------|------|-------------|--------|
| `GET /ops/data-freshness/global?group=operational` | 200 | ~610 | OK |
| `GET /ops/data-pipeline-health?latest_only=true` | 200 | ~592 | OK |
| `GET /ops/plan-vs-real/monthly?country=co&month=2026-04` | 200 | ~69 620 | Lento; sin error |
| `GET /ops/real-lob/monthly-v2?country=co` | 200 | ~1 988 | OK |
| `GET /ops/supply/freshness` | 200 | ~784 | OK |
| `GET /ops/business-slice/omniview?granularity=monthly&period=2026-04&limit_rows=50` | 200 | ~3 916 | Omniview |
| `GET /ops/business-slice/omniview?granularity=weekly&period=2026-04-28&country=pe&limit_rows=50` | 200 | ~3 306 | Omniview + país |
| `GET /ops/driver-lifecycle/weekly?from=2026-04-01&to=2026-05-08` | 200 | ~2 055 | Supply/lifecycle |

**Ningún 500 ni error de relación faltante** en estas rutas.

---

## 5. Errores remanentes (fuera del lag MV)

1. **`audit_trips_2026_commercial_coverage`:** falla umbrales de `comision_empresa_asociada` / `pago_corporativo` en semanas recientes. Es **calidad de datos en fuente** o definición de umbral, **no** stale de `mv_real_lob_*`. Seguimiento: ETL / contrato `trips_2026` o ajuste de política de alerta (fuera de este cierre MV).

2. **`driver_lifecycle_weekly` = DERIVED_STALE** en audit: justificado como granularidad semanal vs fuente diaria (§3). No impide **GO** operacional core acordado.

3. **`trips_base` SOURCE_STALE:** legacy documentado; banner REAL usa grupos operacionales sin depender de `trips_all` para “última fecha”.

---

## 6. Criterio GO / NO-GO

| Criterio | Resultado |
|----------|-----------|
| Omniview con datos y endpoints 200 | **GO** |
| `real_lob` / operational hasta fecha esperada (2026-05-07 en hechos) | **GO** |
| `driver_lifecycle` y `supply_weekly` audit **OK** (weekly lifecycle: ver nota) | **GO** con nota §3 |
| `data_freshness_audit` actualizado (checked_at reciente) | **GO** |
| Vistas rollup/cobertura/revenue summary existentes y consultables | **GO** |
| MV horaria lee `v_real_trip_fact_v2` | **GO** |
| Sin `relation does not exist` en smoke | **GO** |
| Sin hardcodes ni freshness inventada | **GO** (solo lectura audit + APIs existentes) |

**Veredicto: GO** para **cierre del incidente de lag por MV mal enlazada y CASCADE**, con **seguimiento aparte** para auditoría comercial `trips_2026` y eventual ajuste de expectativa `driver_lifecycle_weekly`.

---

## 7. Artefactos

- Validación BD: `backend/scripts/validate_closure_post_fix.py`
- RCA previo: `docs/INCIDENT_FRESHNESS_E2E_RCA_2026-05-08.md`
- Este documento: `docs/INCIDENT_FRESHNESS_CLOSURE_PHASE1_3.md`
