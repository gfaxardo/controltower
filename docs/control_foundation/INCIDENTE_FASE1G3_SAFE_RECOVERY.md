# INCIDENTE FASE 1G.3 — SAFE RECOVERY

## Veredicto Final: ✅ GO

---

## 1. Causa Raíz

La UI mostraba "Sin versiones / Not Found" por dos causas encadenadas:

1. **Config**: `VITE_API_URL=http://127.0.0.1:8000` apuntaba a una app diferente (scout-liq), no a controltower. Controltower corría en puerto 8001.

2. **Runtime fallback**: Cuando el serving fact no tenía datos para un plan_version + grain, el sistema caía a un runtime fallback que consultaba `staging.control_loop_plan_metric_long` y `ops.plan_trips_monthly` contra una DB remota (`168.119.226.236`), causando timeouts >60s y errores 500.

**Fix**: `VITE_API_URL` corregido a puerto 8001. Runtime fallback desactivado para API pública (solo refresh scripts).

---

## 2. Archivos Modificados

### Mantenidos (necesarios Fase 1G.3)

| Archivo | Cambio |
|---------|--------|
| `frontend/.env` | `VITE_API_URL=8001` (corregido) |
| `frontend/src/services/api.js` | +`getServingPlanVersions()` |
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Performance + memo + auto-select serving versions |
| `frontend/src/components/projections/ProjectionVersionSelector.jsx` | Badges materializada/sin fact |
| `frontend/src/utils/performanceTimer.js` | Instrumentación (nuevo) |
| `backend/app/routers/ops.py` | Endpoint `serving-plan-versions` + import |
| `backend/app/services/projection_expected_progress_service.py` | `list_serving_plan_versions()`, `_list_plan_versions_in_serving_fact()`, controlled response |
| `backend/scripts/refresh_omniview_projection_facts.py` | `_allow_runtime_fallback=True` |

### Revertidos / Fuera de alcance

Ninguno. Los archivos mencionados (recoverability, App.jsx, controlTowerNavigationRegistry) venían del `git pull` de rama remota, no de los cambios de Fase 1G.3.

---

## 3. Runtime Fallback — Desactivado para API Pública

### Comportamiento anterior
```
API → serving fact miss → _load_plan_for_projection_scope() → timeout >60s → 500
```

### Comportamiento nuevo
```
API → serving fact miss → 200 controlado:
  projection_exists: false
  fallback_reason: "serving_fact_missing"
  available_plan_versions_in_serving_fact: [...]
  required_refresh_command: "python backend/scripts/..."
```

El path runtime (`_load_plan_for_projection_scope` + build) sigue existiendo y es ejecutable pasando `_allow_runtime_fallback=True`, usado exclusivamente por `refresh_omniview_projection_facts.py`.

---

## 4. Serving Facts por Grain

| Grain | Estado | Rows | served_from | Tiempo |
|-------|--------|------|-------------|--------|
| daily | ✅ materializado | 3,591 | fact | ~3.3s |
| weekly | ✅ materializado | 1,463 | fact | ~1.5s |
| monthly | ❌ no soportado (CHECK constraint) | — | controlled 200 | <1s |

**Nota**: La tabla `serving.omniview_projection_daily_fact` tiene `CHECK (grain IN ('daily', 'weekly'))`. Monthly no puede tener serving facts por diseño. La UI muestra mensaje controlado para monthly en Vs Proyección.

---

## 5. Validación Final

| Escenario | Resultado |
|-----------|-----------|
| daily + plan_version con fact | 3591 rows, served_from=fact, ~3.3s |
| weekly + plan_version con fact | 1463 rows, served_from=fact, ~1.5s |
| daily + plan_version sin fact | 200, projection_exists=false, sin timeout |
| monthly (sin fact por diseño) | 200, projection_exists=false, sin timeout |
| serving-plan-versions endpoint | 1 version: ruta27_2026_04_21, daily+weekly |
| plan/versions endpoint | 10+ versiones |
| control-loop/plan-versions | Vacío (sin datos en staging) |
| Frontend build | OK |
| Backend syntax | OK |

---

## 6. Tiempos Reales

| Operación | Tiempo |
|-----------|--------|
| daily desde serving fact | 3.3s |
| weekly desde serving fact | 1.5s |
| monthly controlled 200 | <100ms |
| refresh weekly (runtime compute) | ~96s (1 sola vez) |
| refresh daily (runtime compute) | ~6s |

---

## 7. Checklist GO/NO-GO

- [x] daily no timeoutea (served_from=fact)
- [x] weekly no timeoutea (served_from=fact)
- [x] monthly no timeoutea (controlled 200)
- [x] Versión sin fact no dispara runtime
- [x] serving-plan-versions devuelve metadata
- [x] UI puede detectar versiones materializadas
- [x] Build frontend OK
- [x] Build backend OK
- [x] `VITE_API_URL` apunta al backend correcto (8001)

**GO ✅**
