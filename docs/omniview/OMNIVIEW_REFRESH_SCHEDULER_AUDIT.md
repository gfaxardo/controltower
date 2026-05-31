# OMNIVIEW REFRESH SCHEDULER AUDIT

**Fecha**: 2026-05-30
**Motor**: Control Foundation

---

## 1. Root Cause Identificada

El APScheduler que ejecuta `run_business_slice_real_refresh_job()` a las 04:00 y `scheduled_daily_refresh()` a las 05:00 requiere que el **backend esté vivo** (proceso corriendo). En entornos donde el backend se inicia bajo demanda (desarrollo, pruebas), los schedulers no se ejecutan a menos que el servidor esté activo 24/7.

Esto explica por qué FACT_DAILY se detuvo en April 30:
- El APScheduler corrió correctamente hasta finales de abril
- El backend se detuvo (por reinicio, crash, o simplemente se cerró la terminal)
- Los schedulers dejaron de ejecutarse
- May 2026 nunca recibió refresh

---

## 2. Auditoría del Código

### 2.1 `backend/app/main.py` (lines 130-212)

```python
if settings.OMNIVIEW_REAL_REFRESH_ENABLED:
    from app.services.refresh_control_service import is_scheduler_enabled
    if not is_scheduler_enabled():
        logger.info("APScheduler NO iniciado...")
    else:
        # Inicia BackgroundScheduler con jobs a 04:00 y 05:00
```

**Issue #1**: `is_scheduler_enabled()` retorna `True` para dev/staging. Pero no verifica si el scheduler realmente se ejecutó. Si el scheduler falla al iniciar (import error, versión incompatible), se captura como `Exception` y se ignora.

**Issue #2**: Los jobs están configurados con `max_instances=1, coalesce=True, misfire_grace_time=600`. Si el backend está caído cuando el job debería ejecutarse (04:00), el misfire se pierde después de 600s (10 min). No hay retry.

**Issue #3**: No hay logging de heartbeat. No hay forma de saber si el scheduler está vivo sin consultar el estado de los datos.

### 2.2 `backend/app/services/business_slice_real_refresh_job.py`

```python
def run_business_slice_real_refresh_job(force=False):
    if not force and _last_refresh_completed_ts > 0:
        elapsed = time.time() - _last_refresh_completed_ts
        if elapsed < min_sec:
            return {"ok": True, "skipped": True, "reason": "cooldown"}  # Silencioso
```

**Issue #4**: El cooldown (15 min por defecto) puede causar que las ejecuciones manuales sean ignoradas sin mensaje explícito.

**Issue #5**: Los errores se capturan por mes (`try/except` en el loop). Si un mes falla, el otro continúa. Esto es resiliente pero los errores pueden quedar sin alertar.

### 2.3 `backend/app/services/serving_refresh_scheduler.py`

```python
def scheduled_daily_refresh():
    subprocess.run([sys.executable, "-m", "scripts.refresh_omniview_projection_facts", ...])
```

**Issue #6**: El refresh de serving facts usa `subprocess.run()`. Si el script falla, el error se captura como `Exception` en el wrapper del scheduler. No hay reintento automático.

---

## 3. Evidencia de Falla

| Indicador | Valor | Significado |
|-----------|-------|-------------|
| `MAX(refreshed_at)` en FACT_DAILY (May) | NULL | Nunca hubo refresh en May |
| `MAX(loaded_at)` en FACT_DAILY (May) | NULL | Nunca hubo carga en May |
| FACT_DAILY última fecha | 2026-04-30 | Abril fue el último mes procesado |
| FACT_WEEKLY última fecha | 2026-03-23 | Marzo fue el último mes con week_fact |
| `OMNIVIEW_REAL_REFRESH_ENABLED` | True | El scheduler está habilitado |
| `ENVIRONMENT` | dev | El scheduler debería estar activo |

**Conclusión**: El backend se detuvo (o se cerró la terminal) en algún momento entre finales de abril y mayo. Los schedulers APScheduler dejaron de ejecutarse. No hay monitoreo que alerte esta condición.

---

## 4. Recomendaciones

1. **Corto plazo**: Ejecutar manualmente el backfill cuando se detecte atraso (scripts ya creados)
2. **Mediano plazo**: Agregar `health/last-refresh` endpoint para monitorear
3. **Largo plazo**: Considerar un cron externo (Windows Task Scheduler / Linux cron) que ejecute el refresh independientemente del backend

