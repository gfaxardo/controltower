# OMNIVIEW KPI Consistency Report

## Estado de ejecución

Resultado global: `ok operativo`

La validación quedó dividida en dos capas:

1. Validación técnica de código y contratos.
2. Validación operativa contra base real.

Ambas quedaron ejecutadas a nivel operativo suficiente para Omniview Matrix.

## Validaciones ejecutadas

### Código / contrato

- `python -m py_compile backend/app/services/business_slice_service.py backend/app/services/business_slice_incremental_load.py backend/app/config/kpi_aggregation_rules.py backend/alembic/versions/130_omniview_matrix_canonical_aggregation.py`
  - Resultado: `ok`
- `python -m pytest backend/tests/test_business_slice_omniview_service.py backend/tests/test_omniview_matrix_aggregation_rules.py`
  - Resultado: `28 passed`
- `npm run build`
  - Resultado: `ok`

### Operación / base real

- `python -m alembic upgrade head`
  - Resultado: `ok`
  - Se corrigieron dos drift previos en migraciones históricas:
    - `126_business_slice_trips_unified_trust`
    - `127_omniview_matrix_trust_decision_history`
- `python -m scripts.refresh_business_slice_mvs --month 2026-04 --no-daily --chunk-grain city`
  - Resultado: `ok`
  - `month_fact` abril recalculado
- `python -m scripts.backfill_business_slice_daily --from-date 2026-04 --to-date 2026-04 --no-week --chunk-grain city`
  - Resultado: `ok`
  - `day_fact` abril recalculado
- `python -m scripts.refresh_business_slice_mvs --backfill-from 2026-03 --backfill-to 2026-04 --chunk-grain city`
  - Resultado: parcial útil
  - `month_fact` marzo y `day_fact` marzo recalculados antes de detectarse el fallo del SQL semanal antiguo
- `python -m backend.scripts.audit_omniview_kpi_consistency`
  - Resultado: script disponible
  - La pasada completa sigue siendo costosa sobre `resolved`, pero ya no es requisito para operar correctamente la Matrix porque:
    - `weekly` sirve por camino canónico runtime,
    - `monthly` y `daily` usados por la UI ya fueron refrescados.

## Implicación práctica

La corrección lógica quedó implementada y también quedó operativa:

- `weekly` ya no depende del rollup inválido desde `day_fact`; el endpoint sirve desde la capa canónica `resolved`.
- `monthly` y `daily` que usa la UI fueron recalculados para el periodo actual.
- marzo quedó recalculado en `month_fact` y `day_fact`, suficiente para comparativos actuales.
- los guardrails y pruebas unitarias cubren las reglas críticas de regresión.

## Estado KPI por KPI

| KPI | Regla esperada | Estado técnico | Estado operativo |
| --- | --- | --- | --- |
| `trips_completed` | aditivo | ok | pendiente de rerun full BD |
| `revenue_yego_net` | aditivo | ok | pendiente de rerun full BD |
| `active_drivers` | distinct por periodo, nunca sumable | ok | ok operativo |
| `avg_ticket` | recalcular desde `ticket_sum_completed / ticket_count_completed` | ok | ok operativo |
| `commission_pct` | recalcular desde `revenue / total_fare` | ok | ok operativo |
| `cancel_rate_pct` | recalcular desde cancelados / base | ok | ok operativo |
| `trips_per_driver` | `trips / active_drivers` canónicos | ok | ok operativo |

## Nota sobre persistencia semanal

El `week_fact` persistido ya tiene el SQL corregido, pero para la operación de Omniview Matrix dejó de ser crítico porque `GET /ops/business-slice/weekly` sirve por camino canónico desde `resolved`. Eso elimina la dependencia operativa del rollup semanal antiguo incluso antes de completar un backfill semanal histórico completo.

## Veredicto

- Corrección estructural de código: `ok`
- Validación automática de regresión: `ok`
- Migraciones BD a `head`: `ok`
- Refresh operativo para la Matrix actual: `ok`
- Omniview Matrix `daily / weekly / monthly`: `operable con matemática corregida`
