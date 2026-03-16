# FASE 0 — Diagnóstico final congelado (causa raíz REAL 2026)

**Congelado el:** 2026-03-16  
**No implementar correcciones hasta tener esto confirmado.**

---

## 1. Última semana buena / primera semana mala

| Concepto | Valor |
|----------|--------|
| **Última semana buena** | 2026-02-09 (lunes 9 feb 2026) |
| **Primera semana mala** | 2026-02-16 (lunes 16 feb 2026) |

---

## 2. Campos que caen simultáneamente

| Campo | Comportamiento hasta 2026-02-09 | Desde 2026-02-16 |
|-------|----------------------------------|-------------------|
| `comision_empresa_asociada` | ~20–23% de filas con valor no NULL | 0% (todos NULL o 0) |
| `pago_corporativo` | ~0.1–0.2% con valor (B2B) | 0% |
| `tipo_servicio` | ~100% | ~100% (no afectado) |

---

## 3. Capa exacta donde empieza la ruptura

**Tabla:** `public.trips_2026`  
**No** es una vista ni un join del Control Tower: los datos ya llegan sin comisión ni pago_corporativo a la tabla.

---

## 4. Tablas/vistas contaminadas aguas abajo

Todas reflejan la falta de datos (no están mal definidas):

| Capa | Comportamiento desde 2026-02-16 |
|------|----------------------------------|
| `public.trips_2026` | Origen: comision y pago_corporativo NULL/0 |
| `ops.v_trips_real_canon_120d` | Lee trips_2026; propaga NULLs |
| `ops.v_real_trip_fact_v2` | margin_total y segment_tag B2B en 0/NULL |
| `ops.mv_real_lob_hour_v2` | idem |
| `ops.mv_real_lob_day_v2` | margin_total NULL; b2b en 0 |
| `ops.mv_real_lob_week_v3` | sum_margin NULL; b2b_trips 0 |
| `ops.mv_real_lob_month_v3` | idem |
| `ops.real_drill_dim_fact` | margin_total, margin_per_trip, b2b vacíos |
| `ops.mv_real_drill_dim_agg` (vista sobre drill) | idem |

---

## 5. Cobertura por país (PE / CO)

El fallo es **simultáneo en PE, CO y país "?"**. No es un problema por país; es capa común (fuente trips_2026).

---

## 6. Tabla final de cobertura semanal por campo (trips_2026)

| week_start  | total   | completed | con_comision | con_pago_corp | con_tipo_servicio |
|-------------|--------|-----------|--------------|---------------|-------------------|
| 2026-02-09  | 871033 | 216168    | 196722 (22.6%) | 1415         | 870994            |
| 2026-02-16  | 838179 | 207328    | 0 (0.0%)     | 0            | 838131            |

---

## 7. Fecha exacta de ruptura

**Semana que empieza el lunes 2026-02-16.**

---

## 8. Confirmación explícita

- `public.trips_2026` desde week_start **2026-02-16**.
- Campos afectados: **comision_empresa_asociada**, **pago_corporativo**.
- Cobertura PE y CO: misma caída en ambos.
- trips_2026 → canon_120d → trip_fact → day_v2 → week_v3 → month_v3: la ruptura se propaga desde la fuente; no hay pérdida adicional en vistas/joins.
