# WEEKLY SERVING GUARDRAILS — CF-H1J.7

## Purpose

Prevenir regresión del pipeline semanal después de CF-H1J.6:

- week_fact quedó desactualizada
- serving sobrevivió con datos huérfanos
- UI mostró datos sin respaldo canónico
- APScheduler falló en silencio

## Canonical Weekly Source

| Layer | Table | Grain |
|-------|-------|-------|
| RAW | `public.trips_2026` | trip |
| day_fact | `ops.real_business_slice_day_fact` | daily |
| **week_fact** | `ops.real_business_slice_week_fact` | **ISO weekly (Monday)** |
| month_fact | `ops.real_business_slice_month_fact` | monthly |
| Serving weekly | `serving.omniview_projection_daily_fact` (grain='weekly') | ISO weekly |

**Canonical source for weekly data:** `ops.real_business_slice_week_fact`

## Serving Weekly Table

- **Table:** `serving.omniview_projection_daily_fact`
- **Filter:** `WHERE grain = 'weekly'`
- **Period key:** `period_key` = ISO Monday (week_start)

## Correct Refresh Command

```bash
cd backend

# Incremental refresh (recomendado)
python -m scripts.refresh_omniview_real_slice_incremental \
  --start-date 2026-04-01 --end-date 2026-05-31 --grain week

# Full operational refresh (vía job)
python -m scripts.refresh_omniview_real_slice --allow-legacy-weekly-dangerous

# Vía API
curl -X POST http://localhost:8000/ops/omniview/refresh?force=true
```

## Prohibited Commands

```bash
# NO-GO: legacy loader sin flag de seguridad
python -m scripts.refresh_omniview_real_slice --force

# NO-GO: backfill incompleto (active_drivers = NULL)
python -m scripts.backfill_week_from_day_fact
```

Estos comandos requieren `--allow-legacy-weekly-dangerous` explícito.

## What "Closed Week" Means

Una semana ISO está **cerrada** cuando:
- Su `week_start` (Lunes) < `week_start` de la semana actual
- Ejemplo: si hoy es Lunes 2026-06-01, la semana cerrada más reciente empieza 2026-05-25

Las semanas en curso (parciales) NO se reconcilian.

## What "Serving Breach" Means

**BREACH**: `serving.omniview_projection_daily_fact` tiene datos para una semana ISO que NO existe en `ops.real_business_slice_week_fact`.

Esto significa que la UI puede mostrar datos semanales que no están respaldados por la fuente canónica.

### Detección

```bash
# Vía API
curl http://localhost:8000/ops/omniview/freshness

# Check de cross-validation
curl http://localhost:8000/ops/omniview/weekly-serving-guardrails?weeks=8
```

La respuesta incluye `cross_validation.findings` con reglas violadas.

## Recovery Checklist

Si se detecta un BREACH:

1. **Identificar semanas faltantes:**
   ```bash
   curl http://localhost:8000/ops/omniview/weekly-serving-guardrails?weeks=8
   ```

2. **Refrescar week_fact:**
   ```bash
   cd backend
   python -m scripts.refresh_omniview_real_slice_incremental \
     --start-date <week_start> --end-date <week_end> --grain week
   ```

3. **Refrescar serving:**
   ```bash
   python -m scripts.refresh_omniview_projection_facts --grain weekly
   ```

4. **Verificar reconciliación:**
   ```bash
   curl http://localhost:8000/ops/omniview/weekly-serving-guardrails?weeks=8
   # Debe devolver status=ok, breach_count=0
   ```

5. **Verificar freshness:**
   ```bash
   curl http://localhost:8000/ops/omniview/freshness
   # Debe devolver status=ok, sin cross-validation findings
   ```

## Scheduler Health

El scheduler debe reportar uno de estos estados explícitos:

| Status | Meaning |
|--------|---------|
| `active` | APScheduler corriendo con jobs registrados |
| `disabled` | CT_SCHEDULER_ENABLED=false (esperado en dev) |
| `missing_dependency` | apscheduler no instalado |
| `error` | Falló al iniciar |

NUNCA debe quedar en `unknown` después de startup.

```bash
curl http://localhost:8000/health | jq .scheduler_status
```

## Guardrails Implemented

| Guardrail | File | Purpose |
|-----------|------|---------|
| Scheduler status | `scheduler_status_service.py` | No silent failure |
| Per-grain freshness | `omniview_freshness_governance_service.py` | raw/day/week/month/serving |
| Cross-validation | `omniview_freshness_governance_service.py` | raw>day, serving>week_fact |
| Fact vs Serving | `weekly_serving_guardrails_service.py` | Metric reconciliation |
| Legacy blocking | `refresh_omniview_real_slice.py` | --allow-legacy required |
| Legacy blocking | `backfill_week_from_day_fact.py` | --allow-legacy required |
| Health exposure | `health.py` | scheduler_status in /health |
| API exposure | `ops.py` | /omniview/weekly-serving-guardrails |
