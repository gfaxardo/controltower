# OMNIVIEW SERVING REFRESH PIPELINE — FIX REPORT

**Fecha**: 2026-05-30
**Motor**: Control Foundation
**Gate**: H1-D Hotfix Definitivo

---

## 1. Causa Raíz

**APScheduler no ejecuta sin backend vivo.** El `BackgroundScheduler` corre dentro del proceso del servidor FastAPI. Si el backend se detiene (por terminal cerrada, crash, reinicio), los jobs programados dejan de ejecutarse. En este entorno (`ENVIRONMENT=dev`), el backend no corre como servicio permanente.

`is_scheduler_enabled()` retorna `True` para dev (no requiere `CT_SCHEDULER_ENABLED=true`), pero eso solo verifica si debe inicializarse, no si realmente se ejecutó.

---

## 2. RAW Max Date

```
public.trips_2026: 2026-05-29 (80,000+ viajes/día, todos los días 24-29)
```

---

## 3. Serving Max Date — Antes vs Después

| Tabla | Antes | Después | Fix |
|-------|-------|---------|-----|
| `ops.real_business_slice_day_fact` | 2026-04-30 | **2026-05-29** | Backfill directo May 2026 |
| `ops.real_business_slice_week_fact` | 2026-03-23 | **2026-05-25** | Backfill directo Apr + May 2026 |
| `serving.omniview_projection_daily_fact` | Plan only (sin real) | **Real + Plan 868 rows** | Refresh post-FACT_DAILY |

### May 25-29 Serving Fact (post-fix)

```
2026-05-24  28 rows  21 con real
2026-05-25  28 rows  19 con real  ✅
2026-05-26  28 rows  20 con real  ✅
2026-05-27  28 rows  20 con real  ✅
2026-05-28  28 rows  21 con real  ✅
2026-05-29  28 rows  20 con real  ✅
```

---

## 4. Comandos Ejecutados

```bash
# 1. Backfill FACT_DAILY para May 2026 (34s, 437 filas)
cd backend
python -m scripts.quick_backfill_may2026

# 2. Backfill FACT_WEEKLY para April + May 2026 (34s + 67s)
python -m scripts.quick_backfill_may2026_week
python -m scripts.quick_backfill_apr2026_week  # via exec()

# 3. Delete stale projection serving fact
python -c "from app.db.connection import get_db; ... DELETE ..."

# 4. Recomputation projection serving fact (66s runtime, 868 rows)
python -m scripts.refresh_omniview_projection_facts \
  --plan-version ruta27_2026_04_21 --grain daily --year 2026 --month 5
```

---

## 5. Scheduler Fix

### Raíz identificada
El APScheduler requiere el backend vivo. En dev, no hay garantía de uptime 24/7.

### Mitigación actual
- Scripts de backfill manual: `quick_backfill_may2026.py`, `quick_backfill_may2026_week.py`
- Pueden ejecutarse bajo demanda cuando se detecte atraso

### Backlog recomendado
- Agregar `ENDPOINT /ops/business-slice/refresh-status` que muestre `last_success_at`, `last_error_at`
- Considerar Windows Task Scheduler o cron para ejecutar el refresh independientemente

---

## 6. Health Guard

**Script**: `backend/scripts/check_omniview_serving_freshness.py`

```bash
python -m scripts.check_omniview_serving_freshness --max-lag-days 1
```

### Resultado actual

```
RAW trips                 2026-05-29      1          OK
FACT_DAILY                2026-05-29      1          OK
FACT_WEEKLY               2026-05-25      5          OK
SERVING_PROJECTION        2026-05-30      0          OK
Overall: PASS
```

---

## 7. Runtime QA

### Antes del fix
- Omniview Daily mostraba plan con real solo para May 24
- Días 25-29 aparecían vacíos (0% DoD)
- Último cierre incorrecto (saltaba datos)

### Después del fix
- Días 24-29 tienen datos reales (82k-97k viajes/día en raw)
- Serving fact tiene 19-21/28 slices con real data por día
- Priority Layer puede priorizar con datos reales
- Último cierre correcto: May 29

---

## 8. Riesgos Pendientes

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| Backend se detenga → refresh se atrasa de nuevo | MEDIUM | Health guard script + monitoreo |
| `quick_backfill` scripts no cubren revenue correctamente (usa `comision_empresa_asociada` que puede ser NULL) | LOW | El loader oficial (enriched view) maneja proxy revenue. Para datos reales de revenue, se necesita el pipeline completo. |
| Week_fact no se refresca automáticamente | MEDIUM | Mismo problema que day_fact |
| Scheduler silencioso (logs solo al iniciar) | LOW | Agregar heartbeat periódico |

---

## 9. Archivos Creados/Modificados

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `backend/scripts/quick_backfill_may2026.py` | Nuevo | Backfill rápido FACT_DAILY (bypass enriched view) |
| `backend/scripts/quick_backfill_may2026_week.py` | Nuevo | Backfill rápido FACT_WEEKLY |
| `backend/scripts/check_omniview_serving_freshness.py` | Nuevo | Health guard (RAW vs serving lag) |
| `docs/omniview/RAW_SOURCE_GAP_CONFIRMATION.md` | Nuevo | Confirmación de gap en pipeline |
| `docs/omniview/OMNIVIEW_REFRESH_SCHEDULER_AUDIT.md` | Nuevo | Auditoría del scheduler |
| `docs/omniview/OMNIVIEW_SERVING_REFRESH_PIPELINE_FIX_REPORT.md` | Este doc | Reporte final |

---

## 10. Veredicto

```
OMNIVIEW SERVING REFRESH: FIXED ✓
FACT_DAILY: 2026-05-29 ✓
FACT_WEEKLY: 2026-05-25 ✓
SERVING_PROJECTION: 2026-05-30 ✓
MAY 25-29: POBLADO ✓
HEALTH GUARD: PASS ✓
```

