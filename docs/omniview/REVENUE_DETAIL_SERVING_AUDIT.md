# REVENUE DETAIL SERVING AUDIT

**Motor:** Control Foundation  
**Fecha:** 2026-05-31  

---

## 1. Tablas Auditadas

### 1.1 Real Business Slice Facts

| Tabla | Revenue Column 1 | Revenue Column 2 | Query en Proyección |
|-------|-----------------|------------------|---------------------|
| `ops.real_business_slice_day_fact` | `revenue_yego_final` | `revenue_yego_net` | `COALESCE(revenue_yego_final, revenue_yego_net)` → `real_revenue` |
| `ops.real_business_slice_week_fact` | `revenue_yego_final` | `revenue_yego_net` | `COALESCE(revenue_yego_final, revenue_yego_net)` → `real_revenue` |
| `ops.real_business_slice_month_fact` | `revenue_yego_final` | `revenue_yego_net` | `COALESCE(revenue_yego_final, revenue_yego_net)` → `real_revenue` |

### 1.2 Projection Serving Fact

| Tabla | Column |
|-------|--------|
| `serving.omniview_projection_daily_fact` | `revenue_yego_net` (almacena el valor real), `revenue_yego_net_projected_total`, `revenue_yego_net_projected_expected`, etc. |

### 1.3 Plan Tables

| Tabla | Revenue Column |
|-------|---------------|
| `ops.v_plan_projection_control_loop` | `projected_revenue` |
| `ops.plan_trips_monthly` (fallback) | `projected_revenue` |

---

## 2. Flujo de Revenue

```
trips_2026 (RAW)
    ↓
refresh_omniview_real_slice.py / APScheduler
    ↓
ops.real_business_slice_day_fact  ← revenue_yego_final / revenue_yego_net
ops.real_business_slice_week_fact  ← revenue_yego_final / revenue_yego_net
ops.real_business_slice_month_fact ← revenue_yego_final / revenue_yego_net
    ↓
refresh_omniview_projection_facts.py (opcional, fast path)
    ↓
serving.omniview_projection_daily_fact ← revenue_yego_net
    ↓
GET /ops/business-slice/omniview-projection
    ↓
Frontend Matrix
```

---

## 3. Posibles Puntos de Pérdida de Revenue

### 3.1 COALESCE con doble NULL

La query de real data usa:
```sql
ABS(COALESCE(revenue_yego_final, revenue_yego_net)) AS real_revenue
```

Si AMBAS columnas son NULL → `real_revenue = NULL` → `revenue_yego_net = None` en API.

**Verificar en DB:**
```sql
SELECT country, city, business_slice_name, trip_date,
       revenue_yego_final, revenue_yego_net
FROM ops.real_business_slice_day_fact
WHERE trip_date >= '2026-05-25'
  AND revenue_yego_final IS NULL
  AND revenue_yego_net IS NULL
ORDER BY trip_date, country, city;
```

### 3.2 Plan Without Real

Si existe plan para una tajada pero no real data, la fila tiene `comparison_status = "plan_without_real"` y `revenue_yego_net = None`.

**Verificar:**
```sql
-- Identificar tajadas con plan pero sin real data para el mes actual
```

### 3.3 Serving Fact Stale

Si `serving.omniview_projection_daily_fact` existe pero está desactualizado, puede no incluir los periodos recientes.

### 3.4 Refresh Pipeline No Ejecutado

En dev, si `CT_SCHEDULER_ENABLED = False` y no se ejecutó refresh manual, la serving fact no se actualiza.

---

## 4. Diagnóstico Recomendado

```sql
-- 1. Revenue por ciudad para los últimos 7 días
SELECT country, city, COUNT(*) as days,
       SUM(COALESCE(revenue_yego_final, revenue_yego_net, 0)) as total_rev,
       COUNT(CASE WHEN revenue_yego_final IS NULL AND revenue_yego_net IS NULL THEN 1 END) as null_days
FROM ops.real_business_slice_day_fact
WHERE trip_date >= CURRENT_DATE - 7
GROUP BY country, city
ORDER BY total_rev DESC;

-- 2. Proyección: cuántas filas tienen revenue null
SELECT period_key, COUNT(*) as total_rows,
       COUNT(CASE WHEN revenue_yego_net IS NULL THEN 1 END) as null_revenue_rows
FROM serving.omniview_projection_daily_fact
WHERE period_key >= '2026-05-01'
GROUP BY period_key
ORDER BY period_key DESC;
```
