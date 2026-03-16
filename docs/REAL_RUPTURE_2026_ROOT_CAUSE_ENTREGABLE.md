# Ruptura común REAL (margen, B2B) desde feb 2026 — Diagnóstico y causa raíz

**Objetivo:** Identificar la causa raíz común por la que desde febrero 2026 fallan a la vez en REAL: margen_total, margen_trip, viajes B2B (y verificar LOB/tipo_servicio).

**Criterio:** No parches por síntoma; diagnóstico con evidencia y plan de recuperación por fases.

---

## FASE 0 — Mapa de campos afectados

| Métrica        | Campo origen                | Vista 1ª aparición              | Join / filtro                         | Hasta day_v2 / week_v3 / month_v3   |
|----------------|-----------------------------|----------------------------------|----------------------------------------|--------------------------------------|
| margen_total   | comision_empresa_asociada    | v_trips_real_canon_120d          | canon → trip_fact (sin join extra)     | v_real_trip_fact_v2.margin_total → hourly → day_v2 |
| margen_trip    | derivado margen / viajes     | Agregado hourly/day              | idem                                   | idem                                 |
| viajes B2B     | pago_corporativo IS NOT NULL| v_real_trip_fact_v2              | segment_tag = 'B2B' en with_lob         | b2b_trips en day_v2 / week_v3 / month_v3 |
| LOB resuelto   | tipo_servicio → dim_*        | v_real_trip_fact_v2              | with_service (tipo_servicio IS NOT NULL); with_lob (dim_service_type, dim_lob_group) | lob_group en agregadas |
| tipo_servicio  | tipo_servicio + normalize    | v_real_trip_fact_v2              | with_service filtra NULL               | real_tipo_servicio_norm               |

**Filtro crítico:** En `v_real_trip_fact_v2`, el CTE `with_service` tiene `WHERE tipo_servicio IS NOT NULL` (y restricciones de longitud). Si `tipo_servicio` es NULL, la fila se pierde en toda la cadena. En la evidencia, `tipo_servicio` se mantiene poblado (~100%), por tanto la ruptura no es por este filtro.

**Fuente de datos 2026:** `v_trips_real_canon_120d` para fechas ≥ 2026-01-01 lee solo de `public.trips_2026`. Si en `trips_2026` faltan `comision_empresa_asociada` o `pago_corporativo`, margen y B2B fallan en toda la cadena.

---

## FASE 1 — Corte temporal exacto

Evidencia ejecutada con `backend/scripts/investigate_real_rupture_2026.py`.

### trips_2026 (fuente raíz)

| week_start  | total   | completed | con_comision | con_pago_corp | con_tipo_servicio |
|-------------|--------|-----------|--------------|---------------|-------------------|
| 2025-12-29  | 447850 | 95045     | 90882 (20.3%)| 498           | 447843            |
| 2026-01-05  | 820014 | 200132    | 190516 (23.2%)| 1713         | 820009            |
| …           | …      | …         | ~20–23%      | 1415–1982     | ~100%             |
| **2026-02-09** | **871033** | **216168** | **196722 (22.6%)** | **1415**   | **870994**        |
| **2026-02-16** | **838179** | **207328** | **0 (0.0%)**   | **0**       | **838131**        |
| 2026-02-23  | 868377 | 209552    | 0 (0.0%)     | 0            | 868349            |
| 2026-03-02  | 885507 | 193816    | 0 (0.0%)     | 0            | 885479            |
| 2026-03-09  | 891753 | 196157    | 0 (0.0%)     | 0            | 891698            |

- **Última semana buena:** 2026-02-09 (lunes 9 feb 2026).
- **Primera semana mala:** 2026-02-16 (lunes 16 feb 2026).

Para **comision_empresa_asociada** y **pago_corporativo** el quiebre es la misma semana; **tipo_servicio** sigue con cobertura ~100% en todas las semanas.

---

## FASE 2 — Cobertura por capa

### 1. Fuente raíz: trips_2026  
Véase tabla anterior. Ruptura visible en semana 2026-02-16.

### 2. v_real_trip_fact_v2  
Refleja exactamente lo mismo: hasta 2026-02-09 hay con_margin y b2b; desde 2026-02-16 con_margin=0 y b2b=0. con_lob se mantiene (tipo_servicio presente).

### 3. mv_real_lob_day_v2  
No se pudo medir en el script (nombre de columna: la MV usa `requested_trips`/`completed_trips`, no `trips`). No cambia la conclusión: la fuente ya viene sin margen/B2B.

### 4. mv_real_lob_week_v3  
- Hasta 2026-02-09: sum_margin distinto de NULL, b2b_trips > 0.  
- Desde 2026-02-16: sum_margin=None, b2b_trips=0.

### 5. mv_real_lob_month_v3  
- 2026-01: sum_margin y b2b_trips presentes.  
- 2026-02: sum_margin y b2b_trips presentes (solo mitad de feb con datos buenos).  
- 2026-03: sum_margin=None, b2b_trips=0.

**Conclusión FASE 2:** El salto donde se pierden los datos es **entre la tabla `trips_2026` y el resto de la cadena**. No hay un salto adicional en canon, trip_fact ni MVs: todas reflejan que desde 2026-02-16 la fuente ya no aporta comisión ni pago_corporativo.

---

## FASE 3 — Campos que se rompen juntos

Null-rate por semana en **trips_2026** (resumen):

| week_start  | pct_comision | pct_pago_corp | pct_tipo_servicio |
|-------------|--------------|---------------|-------------------|
| hasta 2026-02-09 | 20–23%   | 0.1–0.2%      | 100%              |
| 2026-02-16  | **0.0%**     | **0.0%**      | 100%              |
| desde 2026-02-23 | 0.0%     | 0.0%          | 100%              |

**Conclusión:** Comisión y pago_corporativo caen a 0% en la **misma semana (2026-02-16)**. Tipo_servicio no se rompe. Es un indicio fuerte de **causa raíz común** (mismo cambio en la carga o en el sistema origen para esos dos campos).

---

## FASE 4 — Joins y tablas auxiliares

- **Comisión:** No hay join que la aporte; viene directo de `trips_2026.comision_empresa_asociada` vía canon → trip_fact.
- **B2B:** No hay join; viene de `trips_2026.pago_corporativo IS NOT NULL` en trip_fact (with_lob).
- **LOB / tipo_servicio:** Siguen con datos (dim_service_type, dim_lob_group, parks no son la causa de margen/B2B).

**Conclusión:** No es un join que dejó de matchear ni una tabla auxiliar vacía. La tabla **trips_2026** desde la semana del **2026-02-16** deja de recibir valores en `comision_empresa_asociada` y `pago_corporativo` (o se cargan como NULL/0). El fallo está en **quién alimenta trips_2026** (pipeline de ingestión, export, API o ETL externo), no en las vistas ni en el Control Tower.

---

## FASE 5 — PE vs CO

Cobertura por país en **v_real_trip_fact_v2** (resumen):

- Hasta 2026-02-09: pe, co y "?" tienen con_margin y b2b > 0.  
- Desde 2026-02-16: **pe, co y "?"** pasan a con_margin=0 y b2b=0 al mismo tiempo.

**Conclusión:** El problema es de **capa común** (fuente trips_2026), no específico de país. No hay que separar por PE/CO para la causa raíz.

---

## FASE 6 — Impacto en UI

- **margen_total / margen_trip vacíos:** Las agregadas (day_v2, week_v3, month_v3) y el drill leen de la cadena hourly-first, que a su vez lee de `v_real_trip_fact_v2`. Como `margin_total` y por tanto los SUM(margin_total) son NULL/0 desde la fuente para fechas ≥ 2026-02-16, la UI muestra vacío.
- **Viajes B2B en 0 o nulos:** `segment_tag = 'B2B'` depende de `pago_corporativo` en la fuente; desde 2026-02-16 es NULL en trips_2026, luego b2b_trips = 0 en todas las agregadas y en el drill.
- **Cancelaciones:** Siguen existiendo porque vienen de `condicion` (y motivo_cancelacion donde aplique), que no se ha roto.

No es un fallo de la UI ni del drill en sí: el backend y las capas agregadas ya reciben margin y B2B en 0/NULL porque la **fuente** dejó de enviar esos campos.

---

## FASE 7 — Conclusión de causa raíz

1. **¿Existe una causa raíz común?** **Sí.**
2. **¿Cuál es exactamente?** La tabla **public.trips_2026** desde la **semana que empieza el 2026-02-16** ya no recibe datos (o recibe solo NULL/0) en las columnas **comision_empresa_asociada** y **pago_corporativo**. El proceso que inserta o actualiza `trips_2026` (ETL, ingestión, export desde sistema origen) dejó de poblar esas dos columnas a partir de esa fecha.
3. **¿En qué capa empieza?** En la **capa de fuente**: tabla **trips_2026**. No en vistas ni en joins del Control Tower.
4. **¿Qué campos rompe simultáneamente?**  
   - **margin_total / margen_trip** (derivados de comision_empresa_asociada).  
   - **Viajes B2B / segment_tag B2B** (derivados de pago_corporativo).  
   LOB y tipo_servicio **no** se rompen (tipo_servicio sigue al 100%).
5. **¿Desde qué fecha exacta?** Semana que empieza el **lunes 16 de febrero de 2026** (2026-02-16).
6. **¿Qué tablas/vistas quedaron “contaminadas” aguas abajo?** No están mal definidas; simplemente reflejan la falta de datos: **v_trips_real_canon_120d**, **v_real_trip_fact_v2**, **mv_real_lob_hour_v2**, **mv_real_lob_day_v2**, **mv_real_lob_week_v3**, **mv_real_lob_month_v3**, **real_rollup_day_fact**, **real_drill_dim_fact** (drill semanal/mensual). Todas mostrarán margen y B2B en 0/NULL para fechas ≥ 2026-02-16 hasta que la fuente se corrija y se refresque/backfillee.

---

## FASE 8 — Plan de recuperación (mínimo correcto)

No parches aislados en drill ni en UI. El arreglo debe ser aguas arriba.

### 1. Corregir la capa fuente (trips_2026)

- **Identificar** el proceso que escribe en `trips_2026` (pipeline de ingestión, job ETL, export desde sistema operativo, etc.). En el repo del Control Tower no está definido ese proceso; suele estar en otro sistema (Airflow, Fivetran, script de carga, API, etc.).
- **Determinar por qué** desde ~2026-02-16 dejaron de poblarse `comision_empresa_asociada` y `pago_corporativo` (cambio de schema en origen, cambio de mapeo de columnas, filtro nuevo, otra fuente de datos, etc.).
- **Ajustar** ese proceso para que vuelva a rellenar ambas columnas con los valores correctos.

### 2. Backfill de trips_2026

- Re-ejecutar la carga (o re-export + carga) de **trips_2026** para el rango **desde 2026-02-16 hasta la fecha actual**, con la corrección aplicada, de modo que esas filas tengan comision_empresa_asociada y pago_corporativo poblados.

### 3. Capas agregadas (hourly → day → week → month)

- Las **vistas** (canon_120d, v_real_trip_fact_v2) no requieren cambio; ya leen las columnas correctas.
- **Materialized views** que dependen de la cadena real (p. ej. mv_real_lob_hour_v2, mv_real_lob_day_v2, mv_real_lob_week_v3, mv_real_lob_month_v3): después del backfill, ejecutar **REFRESH** según la estrategia del proyecto (refresco completo o por rango si está soportado).
- Si existe un job que construye hourly/day/week/month desde trip_fact o desde las MVs, re-ejecutarlo para el rango 2026-02-16 hasta hoy.

### 4. Drill y UI

- Si el drill se puebla desde day_v2 / week_v3 / month_v3 (p. ej. `populate_real_drill_from_hourly_chain.py`), volver a ejecutar el populate para los periodos afectados (semanas/meses desde 2026-02-16) **después** de haber refrescado las MVs. No hace falta cambiar lógica de drill ni de UI si la causa raíz está resuelta en fuente y agregadas.

### 5. Validación

- Volver a ejecutar `python -m scripts.investigate_real_rupture_2026` y comprobar que, para semanas ≥ 2026-02-16, en trips_2026 aparezcan de nuevo con_comision y con_pago_corp > 0, y en week_v3/month_v3 sum_margin y b2b_trips > 0.
- Revisar en la UI drill semanal/mensual que margen_total, margen_trip y viajes B2B dejen de estar vacíos para ese rango.

---

## Entregable final (resumen)

| Entregable | Resultado |
|------------|-----------|
| Tabla de cobertura semanal por campo clave | trips_2026: con_comision y con_pago_corp pasan de ~20% y ~0.2% a 0% en 2026-02-16; tipo_servicio se mantiene 100%. trip_fact y week_v3/month_v3 reflejan lo mismo. |
| Fecha exacta de quiebre | **Semana que empieza el 2026-02-16** (lunes 16 feb 2026). |
| Capa exacta donde inicia la ruptura | **Tabla pública trips_2026** (capa de fuente). |
| Joins o tablas auxiliares sospechosas | Ninguno; la ruptura es por datos no poblados en la fuente. El proceso que alimenta trips_2026 es el sospechoso. |
| Confirmación causa común margen_total, margen_trip y B2B | **Sí.** Ambos dependen de comision_empresa_asociada y pago_corporativo en trips_2026; ambos dejan de tener datos en la misma semana. |
| Plan de recuperación por fases | 1) Corregir proceso que alimenta trips_2026; 2) Backfill trips_2026 desde 2026-02-16; 3) Refrescar MVs/hourly/day/week/month; 4) Repoblar drill para periodos afectados; 5) Validar con script y UI. |

---

**Script de diagnóstico:** `backend/scripts/investigate_real_rupture_2026.py`  
**Ejecución:** `cd backend && python -m scripts.investigate_real_rupture_2026`
