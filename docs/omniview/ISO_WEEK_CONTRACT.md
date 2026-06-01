# ISO WEEK CONTRACT — Omniview Weekly Serving

**Motor:** Control Foundation  
**Fecha:** 2026-05-31  
**Versión:** 1.0.0  

---

## 1. ISO Week Definition

Omniview uses **ISO 8601 weeks** throughout the entire pipeline:

- **week_start** = Monday 00:00:00 UTC of the ISO week
- **week_end** = Sunday 23:59:59 of the ISO week (`week_start + 6 days`)
- **PostgreSQL:** `date_trunc('week', timestamp)::date` returns Monday (ISO standard)
- **Python:** `d - timedelta(days=d.weekday())` where `d.weekday()=0` for Monday
- **Frontend JS:** `getMondayOfISOWeek(d)` computes Monday start, `weekStart.getDate() + 6` for Sunday

---

## 2. Contract Rules

| # | Rule | Status |
|---|------|--------|
| 1 | Weekly usa semanas ISO (lunes inicio) | **PASS** |
| 2 | week_start debe ser lunes ISO | **PASS** |
| 3 | week_end debe ser domingo ISO (computado on-the-fly, no almacenado) | **PASS** |
| 4 | week_key consistente con ISO year/week (frontend: `S{ISO_WEEK}-{ISO_YEAR}`) | **PASS** |
| 5 | Semana ISO que cruza meses NO se parte | **FAIL en per-month loader**, PASS en incremental |
| 6 | Refresh incremental expande a semanas ISO completas | **PASS** (corregido CF-H1I) |
| 7 | Weekly NO se deriva de day_fact (usa RAW vía `_bs_enriched_month`) | **PASS** |
| 8 | active_drivers semanal: `COUNT(DISTINCT driver_id)` desde RAW acotado | **PASS** |
| 9 | No usar month boundary como corte semanal | **FAIL en per-month loader**, PASS en incremental |
| 10 | Validado con semana que cruza mes (2026-04-27 → 2026-05-03) | **PASS** (incremental) |

---

## 3. Puntos FALLIDOS (Pre-existentes)

### Q5/Q9: Cross-Month ISO Weeks — Per-Month Loader Bug

**Afecta:** `load_business_slice_week_for_month()` y `backfill_runner`.

El loader por mes expande el rango DELETE a semanas ISO completas, pero el INSERT solo tiene datos del mes actual en `_bs_enriched_month`. Resultado: semanas que cruzan meses quedan incompletas (el último mes procesado "gana" con datos parciales).

**Ejemplo:** Semana ISO 2026-04-27 (lunes) a 2026-05-03 (domingo):
- Al procesar abril: DELETE semana completa → INSERT solo abril 27-30
- Al procesar mayo: DELETE semana completa → INSERT solo mayo 1-3
- Estado final: datos incompletos (faltan días del otro mes)

**Mitigación:** Usar refresh incremental `refresh_business_slice_week_range` con rango que cubra la semana completa. El incremental no tiene este bug porque `_materialize_enriched_direct` consulta RAW para el rango completo.

---

## 4. Estructura de la Tabla

```sql
CREATE TABLE ops.real_business_slice_week_fact (
    week_start    DATE,         -- lunes ISO
    country       TEXT,
    city          TEXT,
    business_slice_name TEXT,
    ...
    trips_completed    BIGINT,
    active_drivers     BIGINT,  -- COUNT(DISTINCT driver_id) desde RAW
    revenue_yego_net   NUMERIC,
    revenue_yego_final NUMERIC,
    ...
);
```

**week_end NO se almacena.** Se computa como `week_start + 6 days` en todas las capas de servicio y frontend.

---

## 5. Refresh Recomendado para Week Fact

```bash
# Semana ISO completa (lunes a domingo)
python -m scripts.refresh_omniview_real_slice_incremental \
  --start-date 2026-05-25 \
  --end-date 2026-06-01 \
  --grain week

# Abril completo (cubre todas las semanas ISO de abril, incluyendo cruces)
python -m scripts.refresh_omniview_real_slice_incremental \
  --start-date 2026-04-01 \
  --end-date 2026-05-01 \
  --grain week
```

**NO usar `backfill_runner` ni `load_business_slice_week_for_month`** para producción. Estos tienen el bug Q5/Q9 y producen semanas incompletas en bordes de mes.
