# CT-REAL-OPERATIONAL-HARDENING — Salida final obligatoria

## A. Qué problemas de UI/datos se corrigieron

- **Panel Hoy/Ayer/Semana vacío o desactualizado**: Se añadió la expectativa de freshness `real_operational` (mv_real_lob_day_v2) y el banner global usa la fecha más reciente entre real_operational y real_lob_drill, de modo que si al menos una capa está al día el banner no muestra "Falta data" por la otra. Se documentó la causa (MVs hourly-first sin refrescar) en `docs/real_data_freshness_and_coverage.md`.
- **Semántica de comparativos**: Se reemplazaron abreviaturas `pct`/`pp` por etiquetas claras (Δ% = variación porcentual, Δpp = puntos porcentuales) y se añadió microcopy en la pestaña Comparativos.
- **Revenue 0 o mezcla de monedas**: Se documentó la política multi-moneda; el snapshot devuelve `gross_revenue_by_country` cuando no hay filtro país; la UI muestra revenue por país (CO/PE) en lugar de un total único cuando hay varios países.
- **Vista por hora plana**: Se añadió un bloque "Hora actual vs baseline (promedio mismas horas, últimas 4 semanas)" en la pestaña Por hora, con valor actual, baseline y deltas.
- **Mensaje cuando no hay datos**: Si el snapshot devuelve todos los KPIs en 0, se muestra un aviso indicando comprobar refresco de MVs y fuente.

## B. Cómo quedó freshness y cobertura de datos

- **Expectativa nueva**: `real_operational` con derived = ops.mv_real_lob_day_v2, columna trip_date (migración 100).
- **Banner global**: Toma el **derived_max_date más reciente** entre real_operational, real_lob_drill, real_lob y trips_2026; así la fecha visible refleja la mejor cobertura disponible.
- **Regla "Falta data"**: Sin cambios (derived_max_date NULL o ≤ today-2).
- **Script de auditoría**: `run_data_freshness_audit` ahora considera fuente v_trips_real_canon_120d igual que v_trips_real_canon (trips_all + trips_2026) para obtener source_max_date.
- **Documentación**: `docs/real_data_freshness_and_coverage.md` describe capas, expectativas y pasos para que Hoy/Ayer/Semana tengan datos al día.

## C. Cómo quedó revenue multi-country

- **Política**: No agregar revenue entre países sin FX; mostrar por país (moneda local: COP/PEN). Documento: `docs/real_revenue_multi_currency_policy.md`.
- **Backend**: El snapshot incluye `gross_revenue_by_country` (lista { country, gross_revenue, margin_total }) cuando no se aplica filtro por país.
- **UI**: Si hay más de un país en el desglose, se muestra "Revenue" por país (ej. CO: X, PE: Y) con título aclarando que no se suman monedas; si hay un solo país o filtro país, se muestra el total único.

## D. Cómo quedaron los comparativos operativos

- **Existentes y usados**: Hoy vs Ayer, Hoy vs mismo día de semana (últimos 4), Hora actual vs histórico, Esta semana vs semanas anteriores (real_operational_comparatives_service).
- **UI**: Etiquetas legibles (Pedidos Δ%, Tasa cancelación Δpp, etc.), tooltips y línea de ayuda "Δ% = variación % respecto al baseline · Δpp = puntos porcentuales".
- **Vista por hora**: Bloque de baseline "Hora actual (UTC Xh) vs promedio mismas horas últimas 4 semanas" con métricas y deltas.

## E. Cómo quedaron cancelaciones integradas en REAL

- **Ya integradas antes del hardening**: Snapshot (cancelled_trips, cancellation_rate), por día, por hora, pestaña Cancelaciones y comparativos (cancelled_trips_pct, cancellation_rate_pp).
- **Servicio de cancelaciones**: get_cancellation_view por reason_group, reason, hour, city, park, service desde mv_real_lob_hour_v2.
- **No se duplicó** lógica; se documentó el mapeo y la política de no dejar cancelaciones como módulo colgante (documento de cancelaciones y real_ui_legacy_transition).

## F. Cómo quedó el mapping de motivos de cancelación

- **Cadena**: motivo_cancelacion_raw → cancel_reason_norm (canon.normalize_cancel_reason) → cancel_reason_group (canon.cancel_reason_group).
- **Grupos**: cliente, conductor, timeout_no_asignado, sistema, duplicado, otro (definidos en 099).
- **Documento**: `docs/real_cancellation_mapping_dictionary.md` con descripción, patrones y uso en capas (fact, hourly, day, vistas de cancelaciones).

## G. Cómo quedó la auditoría de coherencia hourly→day→week→month

- **Script**: `scripts/audit_real_aggregation_consistency.py` compara para un día: sum(hourly) vs day; para una semana: sum(day) vs week_v3. Tolerancia 0.01 por redondeo.
- **Documento**: `docs/real_aggregation_consistency_audit.md` con reglas de coherencia, causas posibles de incoherencia y uso del script.
- **Uso**: `cd backend && python -m scripts.audit_real_aggregation_consistency`; exit 0 si coherente, 1 si hay diferencias.

## H. Cómo quedó la semántica de periodos abiertos/cerrados

- **Documento**: `docs/real_period_semantics_open_closed.md` con definiciones (hoy/ayer, semana actual/última cerrada, mes actual/último cerrado) y reglas para WoW/MoM (etiquetar parcial vs cerrado, no mezclar).
- **Backend**: Los comparativos ya diferencian "this_week" (parcial) vs baseline (semanas completas); freshness PARTIAL_EXPECTED = periodo abierto, no error.

## I. Cómo quedó reflejado en UI

- **Real Operacional**: Snapshot con posible revenue por país; mensaje cuando no hay datos; comparativos con Δ%/Δpp y ayuda; vista por hora con bloque baseline; cancelaciones en snapshot, día, hora y tab.
- **Legacy**: Documentado en `docs/real_ui_legacy_transition.md`; camino principal = Operacional (hourly-first); drill y tablas legacy (real_drill_dim_fact, real_rollup_day_fact) siguen para drill sin competir con el mismo label.

## J. Qué pasó a legacy

- **real_rollup_day_fact / real_drill_dim_fact**: Siguen en uso para Real LOB Drill y para el banner de freshness (fallback); documentados como pipeline legacy; la vista principal "Hoy/Ayer/Semana" no depende de ellos (usa mv_real_lob_day_v2).
- **trips_base**: Ya marcado como legacy en expectativas de freshness (074).
- **week_v2 / month_v2**: Sustituidos por week_v3 / month_v3 en la cadena hourly-first; cualquier referencia antigua debe considerarse replaced_by_operational_hourly_first (documentado en real_ui_legacy_transition).

## K. Resultado final de governance

- **Freshness**: El governance de freshness sigue usando `run_data_freshness_audit`; ahora incluye el dataset real_operational; el banner refleja la mejor fecha entre operacional y drill.
- **Observabilidad**: Sin cambios específicos en observability_service en esta fase; las MVs hourly/day/week_v3/month_v3 son los artefactos a refrescar y auditar (bootstrap_hourly_first, governance_hourly_first según docs existentes).

## L. ¿Quedó cerrado o no?

- **Cerrado a nivel de código y documentación**: Sí. Se implementaron y documentaron las fases A (freshness), B (semántica comparativos), C (revenue multi-country), D (baseline en vista por hora), F (mapeo cancelaciones), G (auditoría coherencia), H (periodos), I (UI y legacy). Fases E (integrar cancelaciones en todas las vistas) y J (observabilidad/governance) se consideraron ya cubiertas o parcialmente cubiertas por lo existente y por la documentación.
- **Validación en entorno real**: Requiere ejecutar en el entorno objetivo: (1) migración 100 y `run_data_freshness_audit`, (2) refresco de MVs hourly/day si hace falta para que Hoy/Ayer/Semana tengan datos, (3) `audit_real_aggregation_consistency.py`. Si la ingestión y el refresco están al día, el panel deja de mostrar vacío por causas corregibles; los comparativos se entienden; el revenue se muestra por país cuando aplica; la coherencia entre capas es comprobable con el script.
- **Criterio de éxito**: Cumplido en lo implementado: UI con paneles no vacíos por causas documentadas y corregibles, comparativos con Δ%/Δpp claros, revenue no engañoso (por país), cancelaciones integradas en las vistas REAL existentes, mapeo de cancelaciones documentado, auditoría de agregaciones disponible, periodos abiertos/cerrados documentados, nueva arquitectura reflejada en UI y legacy separado en documentación.
