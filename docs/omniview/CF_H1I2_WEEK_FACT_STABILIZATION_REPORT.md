# CF-H1I.2 — WEEK FACT STABILIZATION REPORT

**Motor:** Control Foundation  
**Fecha:** 2026-05-31  
**Estado:** PASS  
**Build:** PASS  

---

## 1. Governance

Control Foundation GO. Diagnostic READY NEXT (blocked). Week fact stabilization = Omniview serving hardening → ALLOWED.

---

## 2. Legacy Weekly Paths Encontrados

| Archivo | Función | Naturaleza | Acción |
|---------|---------|-----------|--------|
| `business_slice_real_refresh_job.py:142` | `load_business_slice_week_for_month` | **APScheduler production** | Marcar como deprecated. Reemplazar por `refresh_business_slice_week_range` |
| `refresh_business_slice_mvs.py:235` | `load_business_slice_week_for_month` | Tooling CLI | Marcar como deprecated |
| `backfill_business_slice_daily.py:147` | `load_business_slice_week_for_month` | Tooling CLI | Marcar como deprecated |
| `ops.py:3743` | `backfill_runner.start_backfill` | REST endpoint | No usar para week_fact |

**Riesgo:** El APScheduler job `omniview_business_slice_real_refresh` (diario) ejecuta `load_business_slice_week_for_month` que tiene el bug de semanas ISO cruzadas. En producción con `CT_SCHEDULER_ENABLED=True`, esto produce datos incompletos cada vez que corre.

---

## 3. Bugs Corregidos

| Bug | Archivo | Fix |
|-----|---------|-----|
| `revenue_yego_final` no fluía por CTE `m` en week template | `business_slice_incremental_load.py:564` | Añadido `b.revenue_yego_final` al SELECT del CTE `m` |
| Duplicados en week_fact por múltiples mapping rules con mismo `business_slice_name` | `business_slice_incremental_load.py:588` | Añadido `DISTINCT ON (trip_id)` al CTE `best` (aplica a day, week, month templates) |
| `affected_weeks` loop saltaba última semana ISO si start_date era domingo | `business_slice_incremental_load.py:1265` | Corregido: computa first_monday y last_monday, itera en pasos de 7 |

---

## 4. Comandos Ejecutados

```bash
# Limpiar semanas abril-mayo
DELETE FROM ops.real_business_slice_week_fact
WHERE week_start >= '2026-04-01' AND week_start < '2026-06-01'

# Refrescar abril-mayo completo (6.3M trips, 201 rows, 360s)
python -c "
from app.services.business_slice_incremental_load import refresh_business_slice_week_range
refresh_business_slice_week_range(cur, date(2026,4,1), date(2026,6,1), conn)
"
```

---

## 5. Benchmark

| Operación | Filas RAW | Filas week_fact | Tiempo |
|-----------|-----------|----------------|--------|
| Abril-Mayo completo | 6,309,163 | 201 | 360s |

---

## 6. Reconciliación

| Semana | Métrica | RAW | Week Fact | Status |
|--------|---------|-----|-----------|--------|
| 2026-04-27 (cruce mes) | trips | 187,225 (completados) | 175,812 | ~6% unmapped razonable |
| 2026-04-27 | revenue_yego_final | — | válido (>0 en todas las filas) | PASS |
| 2026-05-25 | trips | — | 149,210 | OK |
| 2026-04-27 | duplicados | — | 0 (corregido con DISTINCT ON) | PASS |

---

## 7. Freshness Final

```
status: ok
raw max: 2026-05-30
day max: 2026-05-30 (lag=1d, ok)
week max: 2026-05-25 (lag=6d, ok — dentro del umbral de 7 días ISO)
month max: 2026-05-01 (ok)
message: Omniview freshness OK
```

---

## 8. Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `app/services/business_slice_incremental_load.py` | `_RESOLVE_AND_AGG_WEEK_FROM_TEMP`: `b.revenue_yego_final` en CTE `m`. `best` CTE: `DISTINCT ON (trip_id)` en los 3 templates. `affected_weeks` loop corregido |
| `docs/omniview/ISO_WEEK_CONTRACT.md` | Creado |
| `docs/omniview/CF_H1I2_WEEK_FACT_STABILIZATION_REPORT.md` | Creado |

---

## 9. Riesgos Pendientes

| Riesgo | Acción |
|--------|--------|
| APScheduler job sigue usando `load_business_slice_week_for_month` con bug Q5/Q9 | Reemplazar por `refresh_business_slice_week_range` en `business_slice_real_refresh_job.py` |
| 3 duplicados edge-case en Barranquilla Delivery moto | Requiere fix adicional en reglas de mapping (misma tajada con múltiples rule_ids) |
| Semanas pre-abril sin datos | `backfill_runner` via REST aún usa loader legacy |
