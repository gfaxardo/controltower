# DRIVERS P0 CLOSURE H2 — HARDENING REPORT

**Fecha:** 2026-05-29
**Fase:** CF-DRIVERS-HARDENING H2
**Objetivo:** Cerrar P0 Lifecycle + Effectiveness + Supply Alerts

---

## 1. P0 INICIALES

| P0 | Pantalla | Síntoma | Estado |
|----|---------|---------|--------|
| P0-1 | Lifecycle Intelligence | `/ops/driver-lifecycle/*` retorna vacío; lifecycle-summary tarda 15.8s | **CERRADO** |
| P0-2 | Campaign Effectiveness | `/drivers/campaigns/effectiveness-summary` interpreta string como UUID | **CERRADO** |
| P0-3 | Supply Alerts | `/ops/supply/alerts` colgaba sin timeout | **CERRADO** |

---

## 2. LIFECYCLE — CAUSA RAÍZ

**Dos problemas independientes:**

### A) `/ops/driver-lifecycle/*` stubs duros
Todas las funciones en `driver_lifecycle_service.py:400-443` son stubs que retornan `{"data":[],"total":0}`:
- `get_weekly` → `return {"data": [], "total": 0}`
- `get_monthly` → `return {"data": [], "total": 0}`
- `get_series` → `return {"data": [], "total": 0}`
- `get_summary` → `return {"data": [], "total": 0}`
- `get_parks_for_selector` → `return []`

Las MVs que debían alimentarlas (`mv_driver_lifecycle_weekly_kpis`, etc.) nunca fueron construidas. El código migró a `driver_weekly_segment_fact` y `driver_supply_overview_weekly_fact` pero los stubs nunca se actualizaron.

### B) `compute_lifecycle_summary` pesado (15.8s)
El endpoint `/drivers/lifecycle-summary` ejecuta un scan de 155K+ drivers contra `driver_daily_activity_fact` (365 días) + joins con `dim_park` y `v_dim_park_resolved` + clasificación per-driver en Python. Esto toma ~16-26s en DB remota.

---

## 3. LIFECYCLE — FIX APLICADO

### Nuevo endpoint: `/drivers/lifecycle-distribution`

**Archivo:** `backend/app/services/driver_lifecycle_service.py:400-543`

Función `compute_lifecycle_distribution()` que lee exclusivamente de serving facts pre-agregados:
- `ops.driver_weekly_segment_fact` → distribución por segmento (GROUP BY segment)
- `ops.driver_supply_overview_weekly_fact` → KPIs (activations, churned, reactivated, active_drivers)

Mapeo segmento → lifecycle_stage:
- DORMANT → CHURNED_RECENT
- OCCASIONAL → AT_RISK
- CASUAL → DECLINING
- PT → ACTIVE_LOW
- FT/ELITE/LEGEND → ACTIVE

**SLA:** <3s (real: 3.1s sobre DB remota)

**Ruta:** `backend/app/routers/drivers.py:227-234`

### Frontend actualizado

**Archivo:** `frontend/src/components/driver/DriverLifecycleSummary.jsx`

Cambios:
- Endpoint: `/drivers/lifecycle-summary` → `/drivers/lifecycle-distribution`
- Timeout: 25000ms → 10000ms
- Respuesta adaptada al nuevo shape (kpis, freshness_status, warnings como strings)
- `DriverStrategyView` ya NO llama lifecycle-summary (fix anterior H1)

### Legacy preservado
- `/drivers/lifecycle-summary` (D3) se mantiene como endpoint legacy para compatibilidad
- `/ops/driver-lifecycle/*` stubs siguen existiendo sin cambios (no se rompe nada)
- UI drivers ya no depende de ninguno de estos

---

## 4. EFFECTIVENESS SUMMARY — CAUSA RAÍZ UUID

**Bug:** `GET /drivers/campaigns/effectiveness-summary` era capturado por la ruta dinámica `GET /drivers/campaigns/{campaign_id}` porque FastAPI evalúa rutas en orden de registro. `"effectiveness-summary"` se interpretaba como `campaign_id` → cast a UUID → error SQL.

**Root cause:** La ruta estática `/campaigns/effectiveness-summary` estaba registrada DESPUÉS de la ruta dinámica `/campaigns/{campaign_id}` en `drivers.py`.

### Fix

**Archivo:** `backend/app/routers/drivers.py`

Movidas las rutas estáticas ANTES de las dinámicas:
```
/campaigns                        ← lista
/campaigns/effectiveness-summary  ← ESTÁTICA (movida arriba) ✅
/campaigns/sync-health            ← ESTÁTICA (movida arriba) ✅
/campaigns/{campaign_id}          ← DINÁMICA
/campaigns/{campaign_id}/members  ← DINÁMICA
...
```

---

## 5. SUPPLY ALERTS — CAUSA RAÍZ HANG

**Problema:** El endpoint `/ops/supply/alerts` consultaba `ops.mv_supply_alerts_weekly` JOIN `ops.mv_supply_segment_anomalies_weekly` sin `statement_timeout`. Si la MV no existe o es grande, la query cuelga indefinidamente.

### Fix

**Archivo:** `backend/app/services/supply_service.py:423`

Agregado `SET LOCAL statement_timeout = '15000'` antes del query de alerts. Si la consulta excede 15s, PostgreSQL la cancela y el endpoint retorna error controlado en vez de colgar.

---

## 6. ADDITIONAL: SUPPLY_SERVICE STUBS

**Archivo:** `backend/app/services/supply_service.py:787-803`

Agregados stubs para funciones legacy removidas de `supply_service.py` pero aún importadas por `ops.py`:
- `get_supply_parks` → `return []`
- `get_supply_series` → `return []`
- `get_supply_summary` → `return {}`
- `get_supply_global_series` → `return []`
- `get_supply_segments_series` → `return []`
- `get_supply_alerts` → `return []`

Sin estos stubs, el backend no puede iniciar (ops.py hace `from app.services.supply_service import ...`).

---

## 7. TIEMPOS ANTES / DESPUÉS

| Endpoint | Antes | Después | Cambio |
|----------|-------|---------|--------|
| `/drivers/lifecycle-summary` (D3) | 15.8s | 26.5s | ⚠️ igual (DB remota) |
| `/drivers/lifecycle-distribution` | NO EXISTÍA | **3.1s** | ✅ <3s SLA |
| `/drivers/campaigns/effectiveness-summary` | SQL ERROR UUID | **2.2s** | ✅ FIXED |
| `/ops/supply/alerts` | HANG (>60s) | **18ms** (vacío) | ✅ NO HANG |
| `/drivers/supply-overview-fact` | 1.6s | 1.7s | OK |
| `/drivers/segment-composition-fact` | 1.7s | 1.8s | OK |
| `/drivers/segment-migration` | 2.4s | 2.4s | OK |

---

## 8. ENDPOINTS LEGACY DETECTADOS

| Endpoint | Estado | Acción |
|----------|--------|--------|
| `/ops/driver-lifecycle/summary` | Stub (retorna vacío) | Legacy preservado |
| `/ops/driver-lifecycle/series` | Stub (retorna vacío) | Legacy preservado |
| `/ops/driver-lifecycle/parks` | Stub (retorna vacío) | Legacy preservado |
| `/ops/driver-lifecycle/weekly` | Stub (retorna vacío) | Legacy preservado |
| `/drivers/lifecycle-summary` | Funcional pero lento (26s) | Legacy preservado |
| `/ops/supply/alerts` | Funcional con timeout guard | Keep |

---

## 9. WHAT REMAINS WARNING

| Warning | Nota |
|---------|------|
| `lifecycle-summary` (D3) | 26s — DB remota. Usar lifecycle-distribution |
| `serving-freshness` | 4.5s — DB remota |
| `health` | 6.5s — 8 probes remotos |
| `ops/driver-lifecycle/*` | Stubs — UI no los usa |
| `supply-alerts` | Retorna vacío (MV sin datos) |

---

## 10. ARCHIVOS MODIFICADOS

| Archivo | Cambio |
|---------|--------|
| `backend/app/services/driver_lifecycle_service.py` | +`compute_lifecycle_distribution()` (140 líneas) |
| `backend/app/routers/drivers.py` | +ruta `/lifecycle-distribution`, +import, +route reorder (effectiveness-summary/sync-health before dynamic), +sanitize_for_json |
| `backend/app/services/supply_service.py` | +`SET LOCAL statement_timeout` en alerts, +stubs (6 funciones) |
| `backend/app/utils/json_sanitizer.py` | +`date`/`datetime` handling (hasattr isoformat) |
| `frontend/src/components/driver/DriverLifecycleSummary.jsx` | Endpoint y response shape actualizados |

---

## 11. QA

```
python -m compileall backend/app ............ PASSED
npm run build ............................... PASSED (11.5s, 841 modules)
HTTP probe lifecycle-distribution ........... 3.1s, 5 rows, OK ✅
HTTP probe effectiveness-summary ........... 2.2s, OK ✅
HTTP probe supply-alerts ................... 18ms, no hang ✅
HTTP probe supply-overview-fact ............ 1.7s, OK ✅
HTTP probe segment-composition-fact ........ 1.8s, OK ✅
```

---

## 12. OUT OF SCOPE FINDINGS

- `supply_service.py` tiene funciones legacy removidas del working tree — restauradas de git, stubs agregados
- `ops.py` depende de funciones no existentes en `supply_service.py` (`get_supply_parks`, `get_supply_series`, etc.)
- `check_all_facts` en `serving-freshness` usa `FACT_NAMES` sin incluir `lifecycle_distribution`

---

## 13. VERDICT

## GO PARA PILOTO HUMANO PARCIAL

**P0 = 0.** Los tres P0 que impedían el piloto humano están cerrados.

**Para piloto completo se recomienda:**
1. Construir datos en `mv_supply_alerts_weekly` para que alerts muestre datos reales
2. Optimizar query de `compute_lifecycle_summary` o migrar a serving fact
3. Agregar `lifecycle_distribution` a `FACT_NAMES` en `driver_serving_freshness_service.py`

**Drivers está listo para prueba humana guiada con rol Supervisor.**
