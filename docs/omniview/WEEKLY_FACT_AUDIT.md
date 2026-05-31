# WEEKLY FACT AUDIT — CF-H1F

**Fecha**: 2026-05-31
**Motor**: Control Foundation

---

## 1. Fuente Canónica Weekly

**Tabla**: `ops.real_business_slice_week_fact`

### Pipeline

```
public.trips_2026 (RAW, 90k viajes/día)
  → ops.real_business_slice_day_fact (agregado diario, ~20 filas/día)
    → ops.real_business_slice_week_fact (agregado semanal, DATE_TRUNC week)
      → projection_expected_progress_service._load_real_weekly()
        → GET /ops/business-slice/omniview-projection (grain=weekly)
```

---

## 2. Diagnóstico de Gap

### Antes del fix

| Week Start | Rows | Estado |
|-----------|------|--------|
| 2026-03-23 | 20 | Última poblada |
| 2026-03-30 | 0 | Faltante |
| 2026-04-06 | 0 | Faltante |
| 2026-04-13 | 0 | Faltante |
| 2026-04-20 | 0 | Faltante |
| 2026-04-27 | 0 | Faltante |
| 2026-05-04 | 0 | Faltante |
| 2026-05-11 | 0 | Faltante |
| 2026-05-18 | 0 | Faltante |
| 2026-05-25 | 0 | Faltante |

**9 semanas faltantes (Mar 30 - May 25)**

### Por qué Daily sí y Weekly no

El APScheduler dejó de ejecutar en abril. Cuando se hizo backfill manual de FACT_DAILY (directo desde raw source), los datos diarios quedaron actualizados. Pero FACT_WEEKLY quedó atrasado porque:
1. No se ejecutó backfill de semanas (el script original usaba `get_db_audit()` y los datos no persistieron)
2. El weekly aggregation desde raw source es muy lento (~30 min vs ~2s desde FACT_DAILY)

---

## 3. Backfill Ejecutado

**Script**: `scripts/backfill_week_from_day_fact.py`

Agrega desde FACT_DAILY (ya poblado) usando `DATE_TRUNC('week', trip_date)`.

```bash
python -m scripts.backfill_week_from_day_fact
```

| Mes | Filas | Duración |
|-----|-------|----------|
| April 2026 | 109 | 1.9s |
| May 2026 | 112 | 0.7s |
| **Total** | **221** | **2.6s** |

---

## 4. Validación Post-Backfill

```
FACT_WEEKLY: max = 2026-05-25 (6 días de lag con today=May 31)
```

Estado: OK (lag de 6 días es normal — la última semana cerrada es la del lunes 25)

---

## 5. Consumer Validado

`projection_expected_progress_service._load_real_weekly()` consume `FACT_WEEKLY` (`ops.real_business_slice_week_fact`). No hay tabla legacy involucrada.

---

## 6. Governance Final

```
RAW:        2026-05-29  WARNING (lag 2d, normal)
DAILY:      2026-05-29  WARNING (lag 2d, normal)
WEEKLY:     2026-05-25  OK
MONTHLY:    2026-05-01  OK
PROJECTION: 2026-05-31  OK

Status Global: WARNING
```

El WARNING es aceptable: 2 días de lag para daily es normal (datos hasta anteayer). Ya NO hay BLOCKED.

