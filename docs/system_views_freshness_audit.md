# Auditoría de frescura por vista — YEGO Control Tower

**Fecha:** 2025-03-09  
**Objetivo:** Regla global de "Falta data", auditoría de vistas y visibilidad clara de frescura.

---

## Regla global oficial: "Falta data"

**REGLA ÚNICA PARA TODO EL SISTEMA:**

- **Solo** mostrar estado **"Falta data"** cuando la **última fecha con data del dataset/objeto derivado** es **menor o igual a `current_date - 2`**.
- Es decir:
  - Si `derived_max_date` (o equivalente) es **ayer** → **NO** falta data (estado: Fresca o Parcial esperada).
  - Si `derived_max_date` es **antes de ayer** (o NULL) → **SÍ** falta data.

**Formal:**

- `falta_data = (derived_max_date IS NULL) OR (derived_max_date <= CURRENT_DATE - 2)`
- Equivalente: "Falta data" solo si no hay data hasta ayer; tener data hasta ayer es suficiente para no marcar error.

**Semántica por grano:**

- **Diario:** Falta data si el derivado no llega hasta ayer.
- **Semanal:** La semana actual puede estar abierta (parcial); no marcar "Falta data" solo por eso. Marcar "Falta data" si la última semana con data termina antes de ayer (ej. última data es de hace 2+ días).
- **Mensual:** Igual; mes actual abierto = parcial, no error. Falta data si el derivado no refleja al menos hasta ayer.

Esta regla se aplica en:
- Cálculo de estado por fila (ej. Real LOB drill: estado FALTA_DATA por periodo).
- Indicador global de frescura en UI (banner "Fresca" / "Falta data" / "Atrasada").
- Cualquier vista que muestre estado de datos.

---

## Matriz de auditoría por vista

| view_name | source_object | source_max_date | derived_object | derived_max_date | lag_days | should_show_missing_data | fields_missing | issue_type |
|-----------|---------------|-----------------|----------------|------------------|----------|--------------------------|----------------|------------|
| Real LOB Drill | ops.v_trips_real_canon | (audit) | ops.real_drill_dim_fact → mv_real_drill_dim_agg | MAX(last_trip_ts) por periodo | — | Solo si derived_max_date <= today-2 | — | Estado por fila en Python (expected_loaded_until = yesterday); banner global desde data_freshness |
| Real LOB Daily | ops.v_trips_real_canon | (audit) | ops.real_rollup_day_fact | trip_day | — | Misma regla | — | Consume rollup; freshness desde audit |
| Driver Lifecycle | trips_unified, v_driver_lifecycle_trips_completed | (audit) | mv_driver_lifecycle_base, mv_driver_weekly_stats | last_completed_ts, week_start | — | Misma regla | — | Sin badge "Falta data" por fila; banner global aplica |
| Driver Supply Dynamics | mv_driver_weekly_stats | (audit) | mv_supply_weekly, mv_supply_segments_weekly | week_start | — | Misma regla | — | GET /ops/supply/freshness ya expone last_week; banner global aplica |
| Snapshot | Plan + Real (core, MVs) | — | Varios | — | — | N/A (agregado) | — | Indicador global aplica |
| CoreTable / Plan | plan_repo, core | — | — | — | — | N/A | — | — |

**Nota:** `source_max_date` y `derived_max_date` se obtienen de la última ejecución de `ops.data_freshness_audit` (script `run_data_freshness_audit`). La UI muestra un **banner global** que usa el estado calculado a partir de la auditoría (o de una consulta ligera al derivado principal).

---

## Fuente viva real (resumen)

- **Viajes operativos recientes:** `public.trips_2026` (y vista canónica `ops.v_trips_real_canon` que unifica con trips_all).
- **Fuente consolidada oficial de viajes:** `ops.v_trips_real_canon` (une `trips_all` &lt; 2026-01-01 y `trips_2026` ≥ 2026-01-01). No usar `trips_base` (public.trips_all) como fuente operativa.
- **trips_base (audit):** Dataset legacy. `trips_all` puede estar cortada (ej. hasta 2026-01-31). SOURCE_STALE en trips_base es **esperado**; la fuente viva es `trips_2026`. El estado global del banner **no** se calcula desde trips_base (primario: real_lob_drill).
- **Real LOB:** `ops.v_trips_real_canon` → `real_drill_dim_fact` / `real_rollup_day_fact` → MVs/vistas consumidas por la API.
- **Driver Lifecycle:** `public.trips_unified` → `ops.v_driver_lifecycle_trips_completed` → MVs.
- **Supply:** Derivado de `mv_driver_weekly_stats` y MVs de supply.

Si el derivado está atrasado respecto a la fuente (LAGGING/DERIVED_STALE), la acción es ejecutar refresh/backfill del derivado, no cambiar la regla de "Falta data".

---

## Estados visibles globales (UI)

| Estado interno | Label en UI | Cuándo |
|----------------|-------------|--------|
| OK / fresca | **Fresca** | derived_max_date >= ayer |
| PARTIAL_EXPECTED | **Parcial esperada** | Periodo actual abierto; data al día |
| LAGGING / DERIVED_STALE / 1 día atrás | **Atrasada** | derivado con retraso de 1 día |
| Falta data / 2+ días | **Falta data** | derived_max_date <= today-2 o NULL |
| Sin datos | **Sin datos** | Sin filas en audit o derivado vacío |

---

## Cambios realizados (resumen)

1. **Regla documentada** en este archivo y en `data_freshness_monitoring.md`.
2. **Backend:** `get_freshness_global_status()` y GET `/ops/data-freshness/global` para un único estado + fechas para el banner.
3. **Frontend:** Componente `GlobalFreshnessBanner` que muestra última fecha en vista, estado (Fresca / Parcial esperada / Atrasada / Falta data) y opcionalmente enlace a más detalle; integrado en `App.jsx`.
4. **Real LOB drill:** La lógica de estado por fila ya usaba `expected_loaded_until = yesterday`; se deja explícito en comentario que cumple la regla global (FALTA_DATA solo cuando last_day_with_data < yesterday).
5. **Auditoría:** Este documento con matriz y referencias a lineage; ejecución del script de audit y evidencia queda a cargo de cron/ops.

---

## Comandos útiles

```bash
# Pipeline completo (recomendado): backfill Real LOB + refresh driver + supply + audit
cd backend && python -m scripts.run_pipeline_refresh_and_audit

# Solo auditoría (escribe en ops.data_freshness_audit)
cd backend && python -m scripts.run_data_freshness_audit

# Consultar última auditoría / centro de observabilidad
# GET http://localhost:8000/ops/data-freshness
# GET http://localhost:8000/ops/data-freshness/global
# GET http://localhost:8000/ops/data-pipeline-health
# POST http://localhost:8000/ops/pipeline-refresh  (ejecuta pipeline completo)
```

Mapa del pipeline (fuente viva, derivado, refresh, breakpoint): [data_pipeline_observability_map.md](data_pipeline_observability_map.md).

**Certificación 2026-03-09:** Se ejecutó el pipeline (sin backfill); driver_lifecycle, driver_lifecycle_weekly y supply_weekly pasaron a OK. Se aplicó fix de `statement_timeout=0` en el refresh de driver lifecycle. Evidencia: [pipeline_refresh_certification.md](pipeline_refresh_certification.md).

---

## Fase I — Entregable final

1. **Regla final de "Falta data":** Solo mostrar "Falta data" cuando `derived_max_date` es NULL o `<= current_date - 2`. Documentada en este archivo y en `data_freshness_monitoring.md`.
2. **Vistas auditadas:** Real LOB (Drill, Daily), Driver Lifecycle, Driver Supply Dynamics, Snapshot; matriz en este documento.
3. **Fuente viva por vista:** Ver tabla y `data_freshness_lineage_map.md`; primario para banner: real_lob_drill.
4. **Refresh/backfills:** No se ejecutaron en esta fase; el banner usa la última fila de `ops.data_freshness_audit`. Para que el estado sea correcto hay que ejecutar `python -m scripts.run_data_freshness_audit` (y, si aplica, backfill de MVs).
5. **Campos vacíos:** Sin cambios de propagación en esta fase; la regla y la visibilidad unifican criterio.
6. **Cambios UI:** Banner global `GlobalFreshnessBanner` en `App.jsx` que muestra Estado de datos (Fresca / Parcial esperada / Atrasada / Falta data / Sin datos) y última fecha en vista.
7. **Archivos modificados:** `docs/system_views_freshness_audit.md` (nuevo), `docs/data_freshness_monitoring.md` (regla + endpoint global), `backend/app/services/data_freshness_service.py` (regla, get_freshness_global_status), `backend/app/routers/ops.py` (GET /data-freshness/global), `backend/app/services/real_lob_drill_pro_service.py` (comentario regla), `frontend/src/services/api.js` (getDataFreshnessGlobal), `frontend/src/components/GlobalFreshnessBanner.jsx` (nuevo), `frontend/src/App.jsx` (banner).
8. **Comandos:** Ninguno obligatorio para probar UI; para que el banner muestre datos reales: `cd backend && python -m scripts.run_data_freshness_audit` y opcionalmente `POST /ops/data-freshness/run`.

**Veredicto final: LISTO PARA PROBAR EN UI**

- Regla global documentada y aplicada en backend (global status) y en lógica drill (comentario).
- Frescura muy visible mediante banner en todas las vistas.
- Auditoría documentada; corrección efectiva de refresh/backfill queda a cargo de ejecutar el script de audit (y pipelines existentes).
