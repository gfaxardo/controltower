# Driver Lifecycle — Ejemplo de output tras validaciones optimizadas

Tras los cambios en `scripts.run_driver_lifecycle_build`, el script **no aborta** aunque alguna validación falle o se salte por timeout. Siempre termina con un resumen claro.

## Ejemplo: ejecución exitosa (todas OK)

```
============================================================
1) Build driver_lifecycle_build.sql
============================================================
[INFO] 15 sentencias a ejecutar.
  OK [1] CREATE SCHEMA IF NOT EXISTS ops;
  OK [2] DROP VIEW IF EXISTS ops.v_driver_lifecycle_trips_completed CASCADE;
  ...
============================================================
2) Refresh MVs: ops.refresh_driver_lifecycle_mvs()
============================================================
[OK] refresh_driver_lifecycle_mvs() ejecutado.

============================================================
3) Validaciones
============================================================

--- Validación 1) Activations semanal (diff=0) ---
{'week_start': datetime.date(2025, 2, 24), 'activations_mv': 12, 'activations_direct': 12, 'diff': 0}
{'week_start': datetime.date(2025, 2, 17), 'activations_mv': 8, 'activations_direct': 8, 'diff': 0}
...

--- Validación 2) Activations mensual (diff=0) ---
{'month_start': datetime.date(2025, 2, 1), 'activations_mv': 45, 'activations_direct': 45, 'diff': 0}
...

--- Validación 3) Join coverage trips→drivers (últimos 60d) ---
{'trips_completed_with_driver_60d': 12500, 'trips_matched_60d': 12480, 'pct_trips_mapped_60d': 99.84}

--- Validación 4) TtF min/median/p90 (últimos 3 meses) ---
{'ttf_min': -2, 'ttf_median': 3.0, 'ttf_p90': 14.0, 'outliers_negative': 2}

--- Validación 5) Outliers ttf<0 ---
{'driver_key': 'D001', 'activation_ts': ..., 'registered_ts': ..., 'ttf_days_from_registered': -2}
...

--- Validación 6) Sanity base (reltuples + unique index) ---
{'approx_rows': 1250, 'has_unique_index': True}

--- Validación 7) Unicidad weekly_stats (últimas 12 sem) ---
(0 filas — esperado: sin duplicados)

============================================================
RESUMEN VALIDACIONES
============================================================
  ✓ 1) Activations semanal (diff=0): OK
  ✓ 2) Activations mensual (diff=0): OK
  ✓ 3) Join coverage trips→drivers (últimos 60d): OK
  ✓ 4) TtF min/median/p90 (últimos 3 meses): OK
  ✓ 5) Outliers ttf<0: OK
  ✓ 6) Sanity base (reltuples + unique index): OK
  ✓ 7) Unicidad weekly_stats (últimas 12 sem): OK
------------------------------------------------------------
  OK: 7  |  FAIL: 0  |  SKIPPED: 0
============================================================

Listo.
```

## Ejemplo: validación 3 SKIPPED por timeout (script no aborta)

```
--- Validación 3) Join coverage trips→drivers (últimos 60d) ---
[SKIPPED] timeout: canceling statement due to user request

--- Validación 4) TtF min/median/p90 (últimos 3 meses) ---
{'ttf_min': -1, 'ttf_median': 4.0, ...}
...
============================================================
RESUMEN VALIDACIONES
============================================================
  ✓ 1) Activations semanal (diff=0): OK
  ✓ 2) Activations mensual (diff=0): OK
  ⊘ 3) Join coverage trips→drivers (últimos 60d): SKIPPED — timeout: canceling statement due to user request
  ✓ 4) TtF min/median/p90 (últimos 3 meses): OK
  ...
------------------------------------------------------------
  OK: 6  |  FAIL: 0  |  SKIPPED: 1
============================================================

[WARN] Algunas validaciones fallaron o se saltaron. Revisar resumen.

Listo.
```

## Ejemplo: validación 7 FAIL (objeto no existe)

```
--- Validación 7) Unicidad weekly_stats (últimas 12 sem) ---
[FAIL] relation "ops.mv_driver_weekly_stats" does not exist

============================================================
RESUMEN VALIDACIONES
============================================================
  ...
  ✗ 7) Unicidad weekly_stats (últimas 12 sem): FAIL — relation "ops.mv_driver_weekly_stats" does not exist
------------------------------------------------------------
  OK: 6  |  FAIL: 1  |  SKIPPED: 0
============================================================

[WARN] Algunas validaciones fallaron o se saltaron. Revisar resumen.

Listo.
```

## Cambios aplicados

| Aspecto | Antes | Después |
|---------|-------|---------|
| Fallo en una validación | Abortaba transacción → 4–7 fallaban por "current transaction is aborted" | `rollback()` por validación → continúa con la siguiente |
| Validación 3 (join coverage) | `COUNT(*)` full scan en trips_all | `COUNT` acotado a últimos 60 días (fecha_inicio_viaje) |
| Validación 4 (TtF) | Full scan completo en mv_driver_lifecycle_base | Acotado a últimos 3 meses (last_completed_ts) |
| Validación 6 (sanity) | `COUNT(*)` / `COUNT(DISTINCT)` full scan | `pg_class.reltuples` + verificación de índice único |
| Validación 7 (unicidad) | Full scan en weekly_stats | Acotado a últimas 12 semanas |
| statement_timeout | Global 120s para todo | 30s por defecto; 120s solo en validaciones pesadas (3, 4) |
| Trazabilidad | Sin resumen | Resumen OK/FAIL/SKIPPED con motivo cuando se salta |
