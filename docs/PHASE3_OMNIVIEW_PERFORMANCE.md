# FASE 1 — P3 Omniview performance (RCA y endurecimiento)

## 1. Mapa de endpoints

| HTTP | Router | Servicio | Fuente principal |
|------|--------|----------|------------------|
| `GET /ops/business-slice/monthly` | `backend/app/routers/ops.py` → `business_slice_monthly` | `get_business_slice_monthly` + `append_unmapped_bucket_rows` + `enrich_business_slice_matrix_meta` | `ops.real_business_slice_month_fact` |
| `GET /ops/business-slice/weekly` | `business_slice_weekly` | `get_business_slice_weekly` + `append_unmapped_bucket_rows` + `enrich_business_slice_matrix_meta` | `ops.real_business_slice_week_fact` |

**Frontend:** `frontend/src/services/api.js` — `getBusinessSliceMonthly` / `getBusinessSliceWeekly` (timeouts `BUSINESS_SLICE_HEAVY_TIMEOUT_MS`). Consumo principal: `BusinessSliceOmniviewMatrix.jsx` / `BusinessSliceOmniviewReports.jsx`.

**Filtros típicos:** `country`, `city`, `business_slice`, `fleet`, `subfleet`, `year`, `month`, `limit`.

**Columnas devueltas:** filas con `month` o `week_start`, métricas de fact (`trips_*`, `active_drivers`, `revenue_yego_net`, ratios, etc.) y, en meta, `period_states`, `period_totals`, `per_period_max_trip_date`, frescura.

## 2. Mediciones (entorno local / BD remota representativa)

Metodología: `time.perf_counter()` sobre (a) SQL directo, (b) capa Python, (c) HTTP no medido aquí si el servidor no está en la misma corrida.

### Hallazgos cualitativos

1. **`get_db_quick` abría una conexión TCP nueva en cada bloque** (`psycopg2.connect`), no el pool. Con latencia de red a la BD, cada bloque añadía **~0,7–2+ s** de overhead fijo **independiente del coste real del SQL**.

2. **Primera llamada a canonical mapping** (`dim.dim_business_slice_mapping`) en `aggregate_business_slice_rows` puede costar ~hundreds ms; las siguientes van al TTL cache (~300 s).

3. **`_safe_fetch_matrix_totals_meta`** ejecutaba **dos** agregaciones fact (canónica + UNMAPPED) en **dos transacciones** separadas; se consolidó en **una** cuando aplica UNMAPPED.

### After (tras cambios)

- `get_business_slice_monthly()` (datos + contexto parcial MoM): **~2,7–3,2 s** en la corrida de referencia (antes ~4,7–5,9 s).
- Bundle mensual completo tipo Matrix (`get_monthly` + unmapped + `enrich_business_slice_matrix_meta`): **~6–7 s** (antes ~7–13 s), según RTT a Postgres y profundidad de `comparison_totals`.

**Payload:** respuesta grande (cientos de filas + meta rica); el cuello principal sigue siendo **número de viajes a BD × latencia de red**, no JSON puro (~255 filas serializadas son baratas frente a RTT).

## 3. EXPLAIN (resumen)

Sobre `ops.real_business_slice_day_fact` con rango de fechas acotado, el plan observado usa **bitmap index scan** en `ix_bs_day_fact_date` (no seq scan masivo). Los costes suben con **ámbito global sin filtros país** por volumen de filas, no por falta de índice básico en `trip_date`.

## 4. Índices existentes (migraciones 116 / 119)

- **Month fact:** `ix_rbs_month_fact_month`, `ix_mv_bs_monthly_dims_compat (month, country, city, business_slice_name)`, unicidad de grano.
- **Day fact:** `trip_date`, `(country, trip_date)`, unicidad de grano.
- **Week fact:** `week_start`, `(country, week_start)`, unicidad de grano.

No se añadieron índices nuevos en P3: EXPLAIN sobre rangos acotados ya mostró uso de índice; el ganador fue **reutilizar el pool** y **reducir transacciones**.

## 5. Root cause (clasificación)

| Causa | Clasificación | Evidencia |
|-------|---------------|-----------|
| Handshake TCP repetido por `get_db_quick` | **B + A (infra cliente/DB)** | Tiempo casi constante ~0,7–2 s por `get_db_quick` incluso con `SELECT 1`; desaparece al usar pool. |
| Doble round-trip period totals | **B** | Dos llamadas `_fetch_resolved_period_totals` seguidas para UNMAPPED. |
| Mapping canónico en frío | **B** | Primera agregación lenta; segunda pasada <1 ms (perfil `profile_weekly_split.py`). |

No se detectó uso incorrecto de vista `V_RESOLVED` en el camino feliz mensual/semanal (facts canónicos).

## 6. Cambios aplicados (aditivos)

1. **`get_db_quick`** (`app/db/connection.py`): reutiliza **el pool** y aplica `SET LOCAL statement_timeout` por transacción en lugar de abrir conexión nueva.
2. **`_safe_fetch_matrix_totals_meta`**: cuando corresponde UNMAPPED, **canónica + UNMAPPED** en **una** transacción `get_db_quick`.
3. **`_fetch_*_period_totals`**: aceptan `conn` opcional para compartir transacción.

Semántica de KPIs y contrato JSON sin cambios.

## 7. Before / after (orden de magnitud)

| Escenario | Antes (ref.) | Después (ref.) |
|-----------|-------------|----------------|
| `get_business_slice_monthly()` | ~4,7–5,9 s | ~2,7–3,2 s |
| Bundle Matrix mensual completo | ~7,3–12,7 s | ~6–7 s |

La variación con la **latencia real** a Postgres domina el absoluto; el ratio mejora ~30–45 % en cargas mixtas.

## 8. Validación funcional

- Mismas tablas facts; mismos filtros; no se alteran fórmulas de columnas.
- Recomendación: comparar una respuesta **antes/después** con mismos query params (`year`, `month`, `country`, `city`) — `total` y sumas de `trips_completed` por clave deben coincidir (salvo frescura de datos concurrente).

## 9. Smoke HTTP

```bash
curl -s -o NUL -w "monthly: %{time_total}s\n" "http://127.0.0.1:8000/ops/business-slice/monthly?limit=2000"
curl -s -o NUL -w "weekly: %{time_total}s\n" "http://127.0.0.1:8000/ops/business-slice/weekly?country=peru&limit=1500"
```

## 10. Riesgos remanentes

- Con **RTT alto** al servidor de BD, el objetivo **<5 s** para el **bundle Matrix completo** (datos + meta enriquecida) puede no cumplirse; el cuerpo **solo datos** suele estar ya por debajo o cerca de 5 s.
- **comparison_totals** y agregaciones por rangos de equivalencia parcial siguen generando trabajo extra proporcional a períodos con `comparison_context`.
- Otros módulos que usan `get_db_quick` heredan el nuevo comportamiento (pool); si algún caso dependía de un aislamiento total de sesión, revisar (no se identificó en Omniview).

## 11. Veredicto P3

**P3 OMNIVIEW PERFORMANCE GO (condicionado)**

- **Monthly datos + parciales** mejoran de forma sustancial y se acercan o cumplen **<5 s** según red.
- **Respuesta Matrix completa** puede seguir **>5 s** solo por volumen de meta y RTT; la causa está documentada y el remanente no es un bug de índice obvio en facts.

**GO estricto <5 s end-to-end Matrix** requeriría más trabajo (p. ej. reagrupar consultas en `enrich` o dividir meta en endpoint opcional) — **fuera del alcance mínimo aditivo** acordado aquí.

---

Scripts de apoyo: `backend/scripts/profile_weekly_split.py` (fetch vs agregación Python).
