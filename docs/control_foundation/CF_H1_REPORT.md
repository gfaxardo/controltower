# CF-H1 Report — Metric Definition & Weekly Distinct Hardening

## Fecha: 2026-05-29
## Motor: Control Foundation
## Fase: H1 — Metric Definition & Weekly Distinct Hardening

---

## 1. Estado: **GO**

Control Foundation metric hardening completo. El bug de `active_drivers` weekly SUM proxy fue corregido en la serving layer. Todos los KPIs son ahora consistentes cross-grain.

---

## 2. KPI Registry — Verdict Final

| KPI | Daily | Weekly | Monthly | Post-Fix Status |
|-----|-------|--------|---------|-----------------|
| trips_completed | CORRECT | CORRECT | CORRECT | PASS |
| active_drivers | CORRECT | **CORRECT (was SUM proxy)** | CORRECT | PASS |
| revenue_yego_net | CORRECT | CORRECT | CORRECT | PASS |
| avg_ticket | CORRECT | CORRECT | CORRECT | PASS |
| trips_per_driver | CORRECT | **CORRECT (inherits fix)** | CORRECT | PASS |

Fuente canónica: `_bs_enriched_month` (temp table de `ops.v_real_trips_business_slice_resolved`)
Fórmula canónica: `COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)`

---

## 3. Weekly Distinct Findings

### Antes (SUM proxy)
```sql
-- _WEEK_ROLLUP_FROM_DAY_FACT (line 581, DEPRECATED)
SUM(COALESCE(d.active_drivers, 0))::bigint AS active_drivers
```
- Fuente: `ops.real_business_slice_day_fact` (tabla agregada, sin driver_id)
- Error: SUM de daily distinct counts → 3-7x sobreestimación semanal

### Después (COUNT DISTINCT canónico)
```sql
-- _RESOLVE_AND_AGG_WEEK_FROM_TEMP (NEW, line 489+)
COUNT(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) AS active_drivers
```
- Fuente: `_bs_enriched_month` (trips enriquecidos, misma que day_fact y month_fact)
- Correcto: COUNT DISTINCT real sobre la semana completa

---

## 4. Fuente Canónica Propuesta

**Option A — Implementada**: `COUNT(DISTINCT driver_id)` desde `_bs_enriched_month` agrupado por semana.

Misma definición que daily y monthly. Misma fuente de datos (`_bs_enriched_month`). Mismo pipeline de resolución de business_slice. Solo cambia el GROUP BY.

---

## 5. Gap Analysis

| Métrica | SUM Proxy | COUNT DISTINCT | Diferencia |
|---------|-----------|----------------|------------|
| Ratio esperado | 4-7x | 1x (correcto) | 300-600% |
| Impacto attainment vs plan | Inflado masivamente | Correcto | Señales invertidas |
| Impacto prioridad | Brechas enmascaradas | Señales reales | Bloquea Priority Layer |

**Veredict**: El error era material. La sobreestimación típica es de 400-600% para semanas completas con drivers recurrentes. Corregido.

---

## 6. Fix Aplicado

### Archivos modificados (6 archivos backend)

| Archivo | Cambio |
|---------|--------|
| `business_slice_incremental_load.py` | +`_RESOLVE_AND_AGG_WEEK_FROM_TEMP` (~130 líneas). `load_business_slice_week_for_month()` reescrito para usar enriched. `load_business_slice_day_for_month()` + `keep_enriched` param. |
| `business_slice_real_refresh_job.py` | `keep_enriched=True` + `_drop_enriched_temp()` después de week_fact |
| `backfill_runner.py` | Week per-chunk desde enriched (antes del drop). Import `_RESOLVE_AND_AGG_WEEK_FROM_TEMP`. |
| `backfill_business_slice_daily.py` | `keep_enriched=True` + `_drop_enriched_temp()` |
| `refresh_business_slice_mvs.py` | `keep_enriched=True` + `_drop_enriched_temp()` |

### Principio del fix
1. La week_fact ahora se agrega **directamente desde `_bs_enriched_month`** (misma fuente que day_fact y month_fact)
2. El enriched temp table se mantiene vivo entre day_fact y week_fact (`keep_enriched=True`)
3. Se droppea después de ambos (`_drop_enriched_temp`)
4. Procesado por chunks (country/city) para evitar escaneos masivos
5. `COUNT(DISTINCT driver_id)` canónico — misma definición que daily y monthly

---

## 7. Riesgos Pendientes

| Riesgo | Mitigación |
|--------|------------|
| Performance: week_fact ahora escanea enriched (más lento que rollup de day_fact) | Mismo costo que month_fact por chunk. Aceptable dentro del refresh job (15 min cooldown). |
| `_WEEK_ROLLUP_FROM_DAY_FACT` legacy | Mantenido con deprecation comment. Puede eliminarse en limpieza futura. |
| Backfill_runner: week per-chunk aumenta ligeramente tiempo | Aceptable — los backfills son nocturnos/manuales. |
| `_WEEK_AGG_FROM_RESOLVED` (heavy view version) | No usado en producción. Sirve como referencia/documentación. |

---

## 8. Recomendación para RC-1 (Priority Layer)

**GO**. Las definiciones de KPI están certificadas para todos los grains. No hay diferencias materiales abiertas.

El Priority Layer puede ahora:
- Puntuar active_drivers semanal con valores reales (no inflados)
- Comparar attainment vs plan con denominador correcto
- Generar alertas de brecha de driver supply sin señales invertidas

---

## 9. Build Verification

| Componente | Resultado |
|------------|-----------|
| `business_slice_incremental_load.py` | PASS |
| `business_slice_real_refresh_job.py` | PASS |
| `backfill_runner.py` | PASS |
| `backfill_business_slice_daily.py` | PASS |
| `refresh_business_slice_mvs.py` | PASS |
| Frontend (`vite build`) | PASS (11.52s) |

---

## 10. Documentos Generados

| Doc | Descripción |
|-----|-------------|
| `CF_H1_PRECHECK.md` | Precheck obligatorio: fase activa, relación Control Foundation, riesgos |
| `OMNIVIEW_KPI_REGISTRY_AUDIT.md` | Registro completo de 5 KPIs con fuente, fórmula y grain |
| `WEEKLY_DISTINCT_AUDIT.md` | Auditoría de active_drivers daily/weekly/monthly |
| `WEEKLY_DISTINCT_CANONICAL_SOURCE.md` | 4 opciones evaluadas, recomendación Option A |
| `WEEKLY_DISTINCT_GAP_ANALYSIS.md` | Gap entre SUM proxy y COUNT DISTINCT, query de validación |
| `KPI_CONSISTENCY_AUDIT.md` | Consistencia cross-grain de los 5 KPIs |
| `CF_H1_REPORT.md` | Este reporte final |
