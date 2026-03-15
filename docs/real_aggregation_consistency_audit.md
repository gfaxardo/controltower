# REAL — Auditoría de coherencia entre agregaciones (hourly → day → week → month)

## Objetivo

En la arquitectura hourly-first, **day**, **week** y **month** derivan de la misma fuente **hourly** (mv_real_lob_hour_v2). Las sumas equivalentes para el mismo periodo y filtros deben coincidir (o estar dentro de una tolerancia documentada).

## Reglas de coherencia

Para los mismos filtros (country, city, park, LOB, etc.) y el mismo intervalo de fechas:

1. **sum(hourly) sobre un día** = fila de **day** para ese día.
2. **sum(day) sobre una semana** = total de **week** para esa semana.
3. **sum(day) sobre un mes** = total de **month** para ese mes.
4. **sum(hourly) sobre N días** = sum(day) sobre esos N días.

Métricas a validar como mínimo:

- requested_trips
- completed_trips
- cancelled_trips
- gross_revenue (por país; no mezclar monedas)
- margin_total
- duration_total_minutes

## Posibles causas de incoherencia

- **Filtros distintos**: una vista usa country y otra no.
- **Periodos abiertos vs cerrados**: semana actual (parcial) vs semana cerrada.
- **Timezone**: fechas en UTC vs local.
- **Objetos legacy**: UI o endpoint que aún consuma real_rollup_day_fact o mv_real_lob_week_v2 (antiguo) en lugar de week_v3/month_v3.
- **Semántica de periodos**: week_v3 usa DATE_TRUNC('week', trip_date); day agrupa por trip_date. Debe ser consistente.

## Script de verificación

Ver `scripts/audit_real_aggregation_consistency.py`. Ejecuta consultas que comparan:

- Para un rango de días: SUM desde hourly (por trip_date) vs valores en day.
- Para una semana: SUM(day) vs week_v3.
- Para un mes: SUM(day) vs month_v3.

Las diferencias deben ser 0 (o dentro de tolerancia por redondeo). Si no, el script reporta qué métrica y periodo fallan.

## Acción

Si WoW o MoM muestran contradicciones en la UI:

1. Ejecutar el script de auditoría.
2. Confirmar que la UI usa los endpoints que leen de day_v2 / week_v3 / month_v3.
3. Revisar que no se mezclen periodos parciales con cerrados en el mismo comparativo.
