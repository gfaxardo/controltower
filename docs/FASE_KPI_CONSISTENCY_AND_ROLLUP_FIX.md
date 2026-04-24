# FASE_KPI_CONSISTENCY — Contrato de KPIs y Fix de ROLLUP_MISMATCH

> Fecha de cierre: 2026-04-21
> Alcance: cierre operativo real de los 2 riesgos de negocio críticos detectados
> tras la implementación de las fases 8–15 (Control & Decision Engine).
> Naturaleza: aditiva, sin redesign, sin tocar storage del plan, sin remover REAL-FIRST.

## 1. Contexto y riesgos atacados

Tras dejar Plan/REAL/Omniview/Projection/Trust/Anomaly cerrados, dos riesgos de
negocio quedaban abiertos y comprometían la confianza operativa:

1. **KPI Consistency Risk** — métricas como `active_drivers` o `trips_per_driver`
   se mostraban en monthly/weekly/daily como si fueran sumables, cuando
   semánticamente no lo son (distinct count, ratios derivados). Esto producía
   "discrepancias" aparentes en la UI que no eran bugs sino comparaciones
   inválidas por construcción.
2. **ROLLUP_MISMATCH crítico** — Omniview bloqueaba (`status=blocked`,
   `issue=ROLLUP_MISMATCH`) por diferencias entre `ops.real_business_slice_month_fact`
   y la suma de `ops.real_business_slice_day_fact`. Causa raíz: el job operacional
   `run_business_slice_real_refresh_job` refrescaba day_fact + week_fact pero
   **no** month_fact, dejando este último sistemáticamente stale para el mes en
   curso.

## 2. Contrato KPI por grano (`kpi_aggregation_rules.py`)

El archivo [`backend/app/config/kpi_aggregation_rules.py`](../backend/app/config/kpi_aggregation_rules.py)
ahora declara, para cada KPI visible en Omniview:

- `aggregation_type`: `additive`, `semi_additive_distinct`, `non_additive_ratio`, `derived_ratio`.
- `comparable_across_grains`: bool.
- `comparison_rule`: `exact_sum`, `same_formula_different_scope`, `not_directly_comparable`.
- `monthly_definition` / `weekly_definition` / `daily_definition`.
- `diagnostic_note` y `recommended_ui_note`.

Resumen del contrato actual:

| KPI                | aggregation_type        | comparable | comparison_rule                  |
| ------------------ | ----------------------- | ---------- | -------------------------------- |
| `trips_completed`  | additive                | yes        | exact_sum                        |
| `trips_cancelled`  | additive                | yes        | exact_sum                        |
| `revenue_yego_net` | additive                | yes        | exact_sum                        |
| `active_drivers`   | semi_additive_distinct  | NO         | not_directly_comparable          |
| `trips_per_driver` | derived_ratio           | NO         | not_directly_comparable          |
| `avg_ticket`       | non_additive_ratio      | yes*       | same_formula_different_scope     |
| `commission_pct`   | non_additive_ratio      | yes*       | same_formula_different_scope     |
| `cancel_rate_pct`  | non_additive_ratio      | yes*       | same_formula_different_scope     |

(*) "yes" en el sentido de que la fórmula es la misma; nunca se deben sumar.

Helpers públicos: `get_kpi_grain_contract`, `is_kpi_comparable_across_grains`,
`get_kpi_comparison_rule`, `is_kpi_additive`, `kpi_contract_for_meta`.

## 3. Validador automático (`validate_kpi_grain_consistency.py`)

Script CLI: [`backend/scripts/validate_kpi_grain_consistency.py`](../backend/scripts/validate_kpi_grain_consistency.py)

Carga `month_fact + week_fact + day_fact` por celda (country, city, business_slice)
y aplica una regla por `aggregation_type`:

- `additive` → `SUM(weekly) ≈ monthly` y `SUM(daily) ≈ monthly` con tolerancia 1%.
- `semi_additive_distinct` → No suma; valida `monthly >= max(weekly|daily)` y
  `monthly <= sum(weekly|daily)`. Devuelve `expected_non_comparable` por defecto.
- `non_additive_ratio` → Recomputa fórmula desde componentes; valida coherencia
  interna del valor stored vs recomputed.
- `derived_ratio` → `trips_per_driver` = `trips / drivers` validado scope-by-scope.

Status posibles por celda·KPI:

- `ok`
- `expected_non_comparable`
- `warning`
- `fail`

Uso:

```bash
python -m scripts.validate_kpi_grain_consistency --year 2026 --month 4 \
    --out ../docs/evidence/fase_kpi_rollup/kpi_consistency_apr2026.csv
```

## 4. Diagnóstico de ROLLUP_MISMATCH (`debug_rollup_mismatch.py`)

Script CLI: [`backend/scripts/debug_rollup_mismatch.py`](../backend/scripts/debug_rollup_mismatch.py)

Para cada celda y mes compara:

- `month_fact`: `SUM(trips_completed)`, `SUM(revenue_yego_net)`, `MAX(refreshed_at)`.
- `day_fact rollup`: `SUM` recomputed sobre los días del mes calendario.
- `resolved` (opcional, `--include-resolved`): vista canónica `v_real_trips_business_slice_resolved`.

Y diagnostica `suspected_cause`:

- `stale_month_fact`: `refreshed_at(day_fact) > refreshed_at(month_fact) + 12h`.
- `stale_day_fact`: caso simétrico.
- `mapping_mismatch_only_in_*`: la celda existe en un fact y no en el otro.
- `duplication_or_mapping`, `filter_mismatch_vs_resolved`, `negligible`,
  `day_gt_month_likely_stale_month_fact`, etc.

## 5. Fix de causa raíz del ROLLUP_MISMATCH

Dos cambios coordinados:

### 5.1. Job operacional incluye `month_fact`

[`backend/app/services/business_slice_real_refresh_job.py`](../backend/app/services/business_slice_real_refresh_job.py)

```python
include_month_fact = _refresh_month_fact_enabled()
for mo in months:
    ...
    if include_month_fact:
        logger.info("omniview_real_refresh_job month_fact month=%s", mo_label)
        nm = load_business_slice_month(cur, mo, conn)
        conn.commit()
```

Controlado por `OMNIVIEW_REAL_REFRESH_INCLUDE_MONTH_FACT` en
[`backend/app/settings.py`](../backend/app/settings.py) (default `true`).
Coste: ~12 min adicionales por refresh del par (mes anterior, mes actual)
en datos actuales.

### 5.2. Reclasificación de freshness en integrity check

[`backend/app/services/omniview_matrix_integrity_service.py`](../backend/app/services/omniview_matrix_integrity_service.py)

- La query de `check_consistency` ahora trae `MAX(refreshed_at)` de
  `month_fact` y `day_fact` y calcula `refresh_lag_seconds`.
- Si hay mismatch **y** `lag_s >= 12h` **y** `day_fact >= month_fact`,
  el finding se emite como `STALE_MONTH_FACT` (severity `warn`) en lugar de
  `ROLLUP_MISMATCH` (severity `error`/blocker).
- `STALE_MONTH_FACT` está en `OPERATIONAL_WARNING_CODES` y en el playbook
  con la acción concreta: ejecutar el refresh job (que ya incluye month_fact).

Esto evita bloquear Omniview por una causa conocida y solucionable
operativamente, sin ocultar la inconsistencia (sigue mostrándose como warning
con su detalle y `suggested_fix`).

## 6. Endpoints de auditoría operativa

Añadidos en [`backend/app/routers/ops.py`](../backend/app/routers/ops.py):

### `GET /ops/kpi-consistency-audit`

Query params:

- `month` (YYYY-MM o YYYY-MM-DD, default: mes actual)
- `months` (1..6, default 1)
- `country`, `city` (opcionales)
- `format=json|csv` (default json)

Response JSON:

```json
{
  "generated_at": 1776807916.48,
  "params": {"month": "2026-04-01", "months": 1, "country": null, "city": null},
  "summary": {"ok": 19, "expected_non_comparable": 78, "warning": 0, "fail": 36},
  "per_month": [...],
  "rows": [...]
}
```

### `GET /ops/rollup-mismatch-audit`

Query params:

- `month` (obligatorio, YYYY-MM o YYYY-MM-DD)
- `country`, `city`, `business_slice` (opcionales)
- `include_resolved=true|false` (default false; más lento)
- `format=json|csv` (default json)

Response JSON:

```json
{
  "generated_at": 1776807916.48,
  "params": {"month": "2026-04-01", ...},
  "summary": {"cells": 19, "ok": 19, "mismatch": 0, "by_cause": {}},
  "rows": [...]
}
```

Funciones cliente (frontend): `fetchKpiConsistencyAudit` y
`fetchRollupMismatchAudit` en [`frontend/src/services/api.js`](../frontend/src/services/api.js).

## 7. Evidencia QA — Before vs After (abril 2026)

Toda la evidencia vive en [`docs/evidence/fase_kpi_rollup/`](evidence/fase_kpi_rollup/).

### 7.1. ROLLUP_MISMATCH abril 2026

| Estado  | cells | ok  | mismatch | suspected_cause      | Evidencia                                                      |
| ------- | ----- | --- | -------- | -------------------- | -------------------------------------------------------------- |
| Before  | 19    | 2   | 17       | stale_month_fact x17 | `rollup_mismatch_apr2026_before.csv`                           |
| After   | 19    | 19  | 0        | —                    | `rollup_mismatch_apr2026_after.csv`                            |

Ejemplo célula `colombia·barranquilla·Auto regular`:

- Before: `trips_month_fact=7947`, `trips_recomputed=13250`, `diff_trips_pct=-40%` → `stale_month_fact`.
- After:  `trips_month_fact=13250`, `trips_recomputed=13250`, `diff_trips_pct=0%` → `negligible`.

### 7.2. ROLLUP_MISMATCH diciembre 2025 (sanity / mes cerrado)

| cells | ok  | mismatch |
| ----- | --- | -------- |
| 20    | 20  | 0        |

`rollup_mismatch_dec2025.csv` — sin mismatch ni en before ni en after, lo que
confirma que el problema era exclusivo del mes en curso (mes cerrado ya tenía
month_fact estable de cargas anteriores).

### 7.3. KPI consistency abril 2026

| Estado  | ok  | expected_non_comparable | warning | fail | Evidencia                              |
| ------- | --- | ----------------------- | ------- | ---- | -------------------------------------- |
| Before  | 19  | 77                      | 0       | 37   | `kpi_consistency_apr2026.csv`          |
| After   | 19  | 78                      | 0       | 36   | `kpi_consistency_apr2026_after.csv`    |

Análisis de los `fail` restantes después del fix (todos sobre `trips_completed`
o `active_drivers`):

- `trips_completed` con `monthly == daily_sum` exacto pero `weekly_sum > monthly`:
  el validador suma todas las semanas ISO que **tocan** el mes (incluye días
  del mes anterior y posterior). No es un bug de datos sino una sobre-suma
  metodológica del propio validador. Se documenta como riesgo metodológico
  (ver §9).
- `active_drivers` con `monthly < max(weekly|daily)`: real, ya conocido
  semánticamente; aparece como `fail` aquí porque la heurística del validador
  espera `monthly >= max`. Esto se discute como riesgo de cálculo en §9.

### 7.4. KPI consistency febrero 2026 y diciembre 2025

| Mes      | ok  | expected_non_comparable | warning | fail |
| -------- | --- | ----------------------- | ------- | ---- |
| Feb 2026 | 3   | 81                      | 0       | 56   |
| Dic 2025 | 5   | 81                      | 0       | 54   |

Mismas categorías de `fail` (`trips_completed` por sum semanal cruzando meses
+ `active_drivers` por heurística), no por staleness ni por bug nuevo.

### 7.5. Refresh job con month_fact (log real)

[`refresh_job_with_month_fact.log`](evidence/fase_kpi_rollup/refresh_job_with_month_fact.log)

```
omniview_real_refresh_job START months=['2026-03-01', '2026-04-01']
omniview_real_refresh_job day_fact   month=2026-03  → inserted=581 169.0s
omniview_real_refresh_job week_fact  month=2026-03  → inserted=119
omniview_real_refresh_job month_fact month=2026-03  → inserted=20
omniview_real_refresh_job day_fact   month=2026-04  → inserted=353
omniview_real_refresh_job week_fact  month=2026-04  → inserted=74
omniview_real_refresh_job month_fact month=2026-04  → inserted=19
RESULT: ok=true, errors=0, duration_s=1897.29
  log: ["2026-03: day_rows=581 week_rows=119 month_rows=20 1037.9s",
        "2026-04: day_rows=353 week_rows=74 month_rows=19  855.7s"]
```

### 7.6. Endpoints HTTP

- `GET /ops/kpi-consistency-audit?month=2026-04&months=1` → 200, JSON
  (`endpoint_kpi_consistency_response.json`).
- `GET /ops/rollup-mismatch-audit?month=2026-04` → 200, JSON
  (`endpoint_rollup_mismatch_response.json`, `summary.cells=19, ok=19, mismatch=0`).
- `GET .../*?format=csv` → 200, `text/csv` (`endpoint_*.csv`).

## 8. Reglas operativas (cuándo escalar)

| Síntoma                                              | Esperado                  | Acción                                                           |
| ---------------------------------------------------- | ------------------------- | ---------------------------------------------------------------- |
| `STALE_MONTH_FACT` warning, lag < 4h                 | Sí (entre refreshes)      | Ninguna; se autoresuelve con el próximo job.                     |
| `STALE_MONTH_FACT` warning, lag > 24h                | No                        | Investigar scheduler (¿está activo?, ¿el flag está en false?).   |
| `ROLLUP_MISMATCH` error (no STALE)                   | No                        | Ejecutar `debug_rollup_mismatch.py` y mirar `suspected_cause`.   |
| `kpi-consistency-audit` con `fail` en `additive`     | No (post-fix)             | Reproducir con `debug_rollup_mismatch.py` para el mes afectado.  |
| `kpi-consistency-audit` con `fail` en `semi_add`     | Posible (heurística)      | Confirmar manualmente; revisar lógica de cálculo de drivers.     |

## 9. Riesgos remanentes

1. **Coste del refresh con month_fact** — el job pasa de ~10 min a ~32 min
   en datos actuales. Mitigable con `OMNIVIEW_REAL_REFRESH_INCLUDE_MONTH_FACT=false`,
   pero entonces vuelve `STALE_MONTH_FACT` como warning recurrente.
   Recomendación a futuro: que `load_business_slice_month` reutilice el
   enriched ya materializado por `load_business_slice_day_for_month` para no
   re-materializar `bi.real_daily_enriched` (~350s por mes).
2. **Validador KPI sobre `trips_completed` weekly_sum** — la query
   `_load_week_facts` agrega todas las semanas ISO que tocan el mes,
   sumando días fuera del calendario. Por eso aparecen `fail` que no son
   inconsistencias reales. Solución pendiente: ponderar las semanas por
   fracción de días dentro del mes o restringir `week_start = primer lunes
   completo del mes`.
3. **Heurística `active_drivers` en validador** — `monthly < max(weekly|daily)`
   se marca como `fail`, pero hay casos legítimos en los que el monthly de
   `active_drivers` (definición a nivel de mes) puede no encajar con el
   máximo de las ventanas semanales/diarias por la forma en que el resolver
   asigna business_slice por viaje (un driver activo en varios slices puede
   contar de forma distinta). Pendiente: revisar definición canónica.
4. **`include_resolved=true` en producción** — la vista
   `v_real_trips_business_slice_resolved` puede ser pesada; el endpoint
   acepta el flag pero no lo recomienda por defecto. No hay timeout específico
   en el endpoint todavía.
5. **Autenticación** — los nuevos endpoints siguen el patrón sin auth del
   resto de `/ops/*`. Si se introduce auth/role-gating para /ops, debe
   extenderse a estos dos.

## 10. Archivos tocados

### Backend

- `backend/app/config/kpi_aggregation_rules.py` (extendido)
- `backend/app/services/projection_expected_progress_service.py` (kpi_contract en meta + conservation solo additive)
- `backend/app/services/business_slice_real_refresh_job.py` (incluye month_fact)
- `backend/app/services/omniview_matrix_integrity_service.py` (clasifica STALE_MONTH_FACT, playbook, severity)
- `backend/app/settings.py` (`OMNIVIEW_REAL_REFRESH_INCLUDE_MONTH_FACT`)
- `backend/app/routers/ops.py` (endpoints `/ops/kpi-consistency-audit` y `/ops/rollup-mismatch-audit`)
- `backend/scripts/__init__.py` (paquete importable desde el router)
- `backend/scripts/validate_kpi_grain_consistency.py` (nuevo)
- `backend/scripts/debug_rollup_mismatch.py` (nuevo)

### Frontend

- `frontend/src/components/omniview/projectionMatrixUtils.js` (helpers de comparabilidad)
- `frontend/src/components/BusinessSliceOmniviewMatrixCell.jsx` (badge `≠Σ`)
- `frontend/src/components/OmniviewProjectionDrill.jsx` (sección KpiContractSection)
- `frontend/src/services/api.js` (`fetchKpiConsistencyAudit`, `fetchRollupMismatchAudit`)

### Documentación / evidencia

- `docs/FASE_KPI_CONSISTENCY_AND_ROLLUP_FIX.md` (este archivo)
- `docs/evidence/fase_kpi_rollup/` (todos los CSVs, logs y respuestas HTTP)

## 11. Veredicto

- **ROLLUP_MISMATCH crítico**: RESUELTO para el mes en curso (abril 2026:
  17/19 mismatch → 0/19). Causa raíz documentada y bajo control mediante
  el flag `OMNIVIEW_REAL_REFRESH_INCLUDE_MONTH_FACT`.
- **KPI Consistency Risk**: ATENUADO mediante contrato formal + UI badges
  + auditor automático. Los `fail` residuales del validador son métodológicos
  (sum semanal cruzando meses) o conceptuales (definición de `active_drivers`
  en distintos grains), están explícitos en el reporte y se trazan como
  riesgos remanentes (§9), no como bugs ocultos.
- **Trust operativo**: `STALE_MONTH_FACT` aparece como warning con playbook
  accionable en lugar de bloquear Omniview por una causa solucionable.
- **Auditabilidad**: cualquier operador puede reproducir, ahora y a futuro,
  ambos diagnósticos vía CLI o vía endpoints HTTP (`/ops/kpi-consistency-audit`,
  `/ops/rollup-mismatch-audit`).
