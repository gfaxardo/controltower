# Weekly Distinct Gap Analysis — Active Drivers

## Fecha: 2026-05-29

---

## Methodology

Para cuantificar la diferencia entre `SUM(daily_counts)` (actual) y `COUNT(DISTINCT driver_id)` (canónico), usamos la siguiente relación:

- **SUM proxy** = Σ(active_drivers per day)
- **True weekly distinct** = COUNT(DISTINCT driver_id) across the week

La diferencia depende de la **frecuencia de operación** de los drivers:

| Patrón | SUM | Distinct | Ratio |
|--------|-----|----------|-------|
| Mismos drivers 7/7 días | N × 7 | N | 7.0x |
| Mismos drivers 5/7 días | N × 5 | N | 5.0x |
| Rotación alta (distintos cada día) | N_total_days | N_total_days | 1.0x (mismo) |
| Mixto típico (70% daily repeat) | ~4.9N | ~N | ~4.9x |

---

## Expected Gap (Framework)

Sin acceso directo a la BD, se proporciona la query de validación:

```sql
-- WEEKLY CORRECT (desde enriched trips)
WITH week_canonical AS (
    SELECT
        date_trunc('week', trip_date)::date AS week_start,
        country,
        city,
        business_slice_name,
        COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag) AS active_drivers_canonical
    FROM ops.v_real_trips_business_slice_resolved
    WHERE trip_date >= '2026-03-01'
      AND (NOT is_subfleet OR is_subfleet IS NULL)
    GROUP BY 1, 2, 3, 4
),
-- WEEKLY CURRENT (desde week_fact)
week_current AS (
    SELECT
        week_start,
        country,
        city,
        business_slice_name,
        active_drivers AS active_drivers_current
    FROM ops.real_business_slice_week_fact
    WHERE week_start >= '2026-03-01'
      AND (NOT is_subfleet OR is_subfleet IS NULL)
)
SELECT
    c.week_start,
    c.country,
    c.city,
    c.business_slice_name,
    c.active_drivers_canonical,
    w.active_drivers_current,
    w.active_drivers_current - c.active_drivers_canonical AS abs_diff,
    ROUND((w.active_drivers_current::numeric / NULLIF(c.active_drivers_canonical, 0) - 1) * 100, 1) AS pct_diff
FROM week_canonical c
JOIN week_current w USING (week_start, country, city, business_slice_name)
WHERE c.active_drivers_canonical > 0
ORDER BY pct_diff DESC;
```

---

## Expected Results by Scope

### Peru, Lima, Auto regular (línea principal)

| Scenario | Expected SUM | Expected Distinct | Expected Ratio |
|----------|-------------|-------------------|----------------|
| Full week (7 days, same drivers) | ~700 | ~100 | 7.0x |
| Partial week (4 days) | ~400 | ~100 | 4.0x |
| Mixed week (variable attendance) | ~550 | ~110 | 5.0x |

### Last 4 weeks (expected)
| Week | Current (SUM proxy) | Canonical (distinct) | Abs Diff | % Diff |
|------|---------------------|---------------------|----------|--------|
| 2026-04-28 | Inflado | Correcto | Significativo | ~300-600% |
| 2026-05-05 | Inflado | Correcto | Significativo | ~300-600% |
| 2026-05-12 | Inflado | Correcto | Significativo | ~300-600% |
| 2026-05-19 | Inflado | Correcto | Significativo | ~300-600% |

---

## Impacto Operacional

### Attainment vs Plan (weekly projection)
Si el plan semanal = 100 drivers esperados:
- **Current (SUM proxy)**: real = 550 → attainment = 550% → señal = green
- **Canonical (true distinct)**: real = 110 → attainment = 110% → señal = green (pero apenas)

La diferencia es material pero puede ser sutil:
- Si el plan ya está calibrado al SUM proxy, el attainment es coherente (aunque el valor absoluto no)
- Si el plan es un `COUNT(DISTINCT)` mensual distribuido → hay mismatch entre definición de plan y definición de real

### Priority Scoring
Para active_drivers en weekly grain:
- Gap absoluto = plan(100) - real(550) = -450 (negativo = "sobre plan")
- Prioridad: baja (parece que vamos bien)
- Realidad: real(110) - plan(100) = +10 → ligero sobre plan

El scoring invierte la señal: de "sobre plan masivo" (SUM proxy) a "ligeramente sobre plan" (canónico).

### Alerting
- Alertas de brecha: no se dispararían para active_drivers weekly (porque SUM proxy las enmascara)
- Esto puede ocultar deterioros reales de driver supply

---

## Verdict

| Aspecto | Severidad |
|---------|-----------|
| Diferencia absoluta | ALTA (300-600%) |
| Diferencia % | ALTA |
| Impacto en attainment | MEDIO (plan puede estar calibrado al SUM) |
| Impacto en prioridad | ALTO (señales de brecha enmascaradas) |
| Impacto en decisión operativa | ALTO (datos inflados → falsa confianza) |
| Bloquea Priority Layer | **SI** — los scores semanales de active_drivers no serían confiables |

### Recomendación: **HARDEN WEEKLY DISTINCT ANTES DE PRIORITY LAYER**
